# Peplink RPi Dashboard

Minimal Flask web app that logs into a Peplink router (session/cookies) and renders a lightweight ops dashboard designed for a 7" Raspberry Pi display. The browser never talks to the router directly — the Flask backend proxies all API calls using a logged-in `requests.Session()`.

## Features

- Session-gated router access (forces login if router session expired after reboot)
- Dashboard widgets:
  - WAN status (active link, state, uptime; tech view shows IP/GW/DNS)
  - Clients (online count; tech view shows IP/MAC/lease)
  - AP status + AP ON/OFF toggle
  - Optional (Tech view): LAN profiles, WAN allowance, SpeedFusion/PepVPN
- UI controls:
  - **Tech ON/OFF** (hides technical fields for small screens)
  - **Light/Dark theme**
  - Defaults: **Tech OFF**, **Theme Light**
- Designed to be readable on a **7" Raspberry Pi display**

## Requirements

- Python 3.10+
- Network access from the Pi to the router (default: `https://192.168.50.1`)

## Install

git clone https://github.com/Audxius/Peplink-RPI-Dashboard.git
cd Peplink-RPI-Dashboard
python -m venv .venv
source .venv/bin/activate
python app.py
