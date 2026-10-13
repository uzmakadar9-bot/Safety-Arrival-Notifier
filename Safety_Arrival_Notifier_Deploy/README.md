# Safety Arrival Notifier

A college mini-project built with Python Flask, SQLite, HTML, CSS and JavaScript.

## Main features
- Registration and login
- User profile and trusted contact
- Destination selection directly on an interactive map
- Start/stop journey
- Browser GPS tracking
- Automatic latitude/longitude selection from the map
- ETA calculation
- Arrival detection
- Risk score:
  - Route deviation: +25
  - Long stoppage: +20
  - Major delay: +20
  - 0-24 Normal
  - 25-49 Attention Needed
  - 50+ High Risk
- Safe-arrival, delay, high-risk and SOS alerts
- Alert history
- Optional Twilio SMS backup

## Important demo note
The risk rules are intentionally simple because the project specification describes a simple risk-score system. The app also includes demo buttons to simulate route deviation, long stoppage and major delay so that a college student can demonstrate the system without physically creating those conditions.

## Installation
1. Install Python 3.11 or newer.
2. Open this folder in VS Code.
3. Open Terminal.
4. Create a virtual environment:
   - Windows: `python -m venv venv`
5. Activate it:
   - PowerShell: `venv\Scripts\Activate.ps1`
   - CMD: `venv\Scripts\activate`
6. Install packages:
   - `pip install -r requirements.txt`
7. Run:
   - `python app.py`
8. Open:
   - `http://127.0.0.1:5000`

## Database
The SQLite database `safety_arrival.db` is created automatically the first time the app starts.

## SMS
SMS is optional. Copy `.env.example` to `.env` and fill Twilio credentials only if you have an approved/test account. The core project works without SMS.

## Browser GPS
When starting a journey, allow location permission in the browser. GPS works best on localhost or HTTPS. For a classroom demo, you can use the simulator buttons if GPS is unavailable.

## Project structure
safety_arrival_notifier/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── profile.html
│   └── history.html
└── static/
    ├── style.css
    └── app.js

## Map and automatic coordinates

You do NOT need to calculate latitude and longitude manually.

On the Dashboard:
1. Click a point on the map.
2. The application automatically fills Latitude and Longitude.
3. Enter a destination name.
4. Click Start Journey.

You can also click **Use My Current Location**. The browser asks for location permission, finds the device location and automatically fills the coordinates.

The map uses Leaflet with OpenStreetMap map tiles. An internet connection is required for the map tiles.


## Deployment notes (Render)
- Start command: `gunicorn wsgi:app`
- Set `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ADMIN_RECOVERY_CODE` as Render environment variables. Use unique, strong values; never commit real values to GitHub.
- The local SQLite database is intentionally not included in this deployment package. A fresh database will be initialized on startup.
- On Render's default ephemeral filesystem, SQLite data is not guaranteed to survive service restarts/redeploys. Use persistent storage or a hosted database for data that must be retained.
- Browser GPS requires HTTPS and the visitor's permission. Test SOS and notifications; do not treat this student project as a verified emergency-response service.
