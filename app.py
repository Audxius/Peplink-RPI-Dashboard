import os
import json
import threading
import requests
import urllib3

from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify
from peplink import PeplinkClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

ROUTER_BASE = os.environ.get("PEPLINK_BASE_URL", "https://192.168.50.1")
LOGIN_ENDPOINT = os.environ.get("PEPLINK_LOGIN_ENDPOINT", "/api/login")

router_session = requests.Session()
router_lock = threading.Lock()
peplink = PeplinkClient(ROUTER_BASE, router_session, router_lock)


def router_login(username: str, password: str) -> dict:
    """
    Attempts to log into the router and returns JSON.
    Adjust payload format if your firmware expects form data, different keys, CSRF, etc.
    """
    url = ROUTER_BASE.rstrip("/") + LOGIN_ENDPOINT
    payload = {"username": username, "password": password}

    with router_lock:
        resp = router_session.post(url, json=payload, verify=False, timeout=10)

    try:
        info = resp.json()
    except Exception:
        raise RuntimeError(
            f"Login response was not JSON. HTTP {resp.status_code}. Body (first 400 chars): {resp.text[:400]}"
        )
    return info


def router_auth_ok() -> bool:
    """
    Lightweight auth probe. If router cookies are missing/expired, this should 401/403.
    Choose an endpoint that is cheap and always present on your unit.
    """
    try:
        _ = peplink.get_json("/api/cmd.ap", ttl=0)
        return True
    except PermissionError:
        return False
    except Exception:
        # If endpoint errors for other reasons, treat as not-authenticated
        # (forces re-login rather than showing a broken dashboard)
        return False


def ensure_router_auth_or_logout() -> bool:
    """
    Returns True if router session is valid. If invalid, clears Flask session.
    """
    if not session.get("logged_in"):
        return False
    if not router_auth_ok():
        session.clear()
        return False
    return True


def require_login_or_401():
    """
    For API routes: enforce both Flask login + router session validity.
    """
    if not session.get("logged_in"):
        return jsonify({"error": "not_logged_in"}), 401
    if not router_auth_ok():
        session.clear()
        return jsonify({"error": "router_session_expired"}), 401
    return None


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already valid, go to dashboard
    if request.method == "GET" and ensure_router_auth_or_logout():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash(("Missing username or password.", "error"))
            return render_template("login.html")

        try:
            info = router_login(username, password)
        except Exception as e:
            flash((str(e), "error"))
            return render_template("login.html")

        if info.get("stat") != "ok":
            # Make this explicit; you can also display info.get("msg") if present.
            msg = info.get("msg") or info.get("message") or "Invalid username or password."
            flash((msg, "error"))
            return render_template("login.html", raw=json.dumps(info, indent=2))

        # Sanity check: ensure the router session now works
        session["logged_in"] = True
        if not router_auth_ok():
            session.clear()
            flash(("Login succeeded but session probe failed. Check login endpoint/payload.", "error"))
            return render_template("login.html", raw=json.dumps(info, indent=2))

        flash(("Logged in.", "ok"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    # Key fix: don’t show dashboard unless router session is valid.
    if not ensure_router_auth_or_logout():
        return redirect(url_for("login"))
    return render_template("dashboard.html")


# ----------------------------
# Core dashboard proxy routes
# ----------------------------

@app.route("/api/wan")
def api_wan():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/status.wan.connection", ttl=2))


@app.route("/api/wan_allowance")
def api_wan_allowance():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/status.wan.connection.allowance", ttl=10))


@app.route("/api/wan_config")
def api_wan_config():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/config.wan.connection", ttl=300))


@app.route("/api/wan/priority", methods=["POST"])
def api_wan_priority():
    err = require_login_or_401()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    return jsonify(peplink.post_json("/api/config.wan.connection.priority", payload=body))


@app.route("/api/clients")
def api_clients():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/status.client", ttl=10))


@app.route("/api/lan_profiles")
def api_lan_profiles():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/status.lan.profile", ttl=10))


@app.route("/api/pepvpn")
def api_pepvpn():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/status.pepvpn", ttl=2))


@app.route("/api/ap")
def api_ap():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/cmd.ap", ttl=2))


@app.route("/api/ap/toggle", methods=["POST"])
def api_ap_toggle():
    err = require_login_or_401()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    return jsonify(peplink.post_json("/api/cmd.ap", payload=body))


@app.route("/api/location")
def api_location():
    err = require_login_or_401()
    if err:
        return err
    return jsonify(peplink.get_json("/api/info.location", ttl=10))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
