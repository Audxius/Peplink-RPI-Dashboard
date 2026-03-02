import time
import threading
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TTLCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._store = {}  # key -> (expires_at, value)

    def get(self, key):
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            exp, val = item
            if now >= exp:
                self._store.pop(key, None)
                return None
            return val

    def set(self, key, val, ttl):
        with self._lock:
            self._store[key] = (time.time() + ttl, val)


class PeplinkClient:
    def __init__(self, base_url: str, session: requests.Session, lock: threading.Lock):
        self.base_url = base_url.rstrip("/")
        self.s = session
        self.lock = lock
        self.cache = TTLCache()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def get_json(self, path: str, ttl: float = 0):
        key = f"GET:{path}"
        if ttl > 0:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        with self.lock:
            r = self.s.get(self._url(path), verify=False, timeout=10)

        if r.status_code in (401, 403):
            raise PermissionError(f"Not authorized for {path} (HTTP {r.status_code})")

        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text, "status_code": r.status_code}

        if ttl > 0:
            self.cache.set(key, data, ttl)
        return data

    def post_json(self, path: str, payload=None):
        with self.lock:
            r = self.s.post(self._url(path), json=(payload or {}), verify=False, timeout=10)

        if r.status_code in (401, 403):
            raise PermissionError(f"Not authorized for {path} (HTTP {r.status_code})")

        try:
            return r.json()
        except Exception:
            return {"raw": r.text, "status_code": r.status_code}
