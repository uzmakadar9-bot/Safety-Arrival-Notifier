# Safety Arrival Notifier — College Fresher Understanding Document

## 1. Project idea

The Safety Arrival Notifier is a travel-safety application. The project specification says that it monitors a journey using GPS and ETA, detects unusual journey conditions using a simple risk score, displays the safety level using colors, and alerts a trusted contact when the risk becomes High Risk.

Source basis: the supplied mini-project document describes GPS/ETA monitoring, the three risk conditions, alert modules, database storage, and the chosen technologies. See the source lines covering the overview and main modules.

## 2. Technology stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | HTML | Page structure |
| Frontend | CSS | Design and responsive layout |
| Frontend | JavaScript | Buttons, GPS calls, API communication |
| Backend | Python + Flask | Routes, business logic and APIs |
| Database | SQLite | Users, journeys, GPS points and alerts |
| Optional notification | Twilio | SMS integration in a production/demo extension |

These choices follow the project specification.

## 3. Architecture

Browser
→ HTML/CSS/JavaScript
→ Flask routes/API
→ SQLite database

For GPS:
Browser Geolocation API
→ `/api/journey/update`
→ distance calculation
→ ETA
→ risk calculation
→ alert record

## 4. Important modules

### A. Login & Profile
Stores:
- name
- email
- hashed password
- phone
- trusted contact name
- trusted contact phone

### B. Journey & Tracking
The user:
1. enters destination name
2. enters destination latitude/longitude
3. clicks Start Journey
4. browser requests GPS permission
5. JavaScript sends location to Flask every 10 seconds
6. Flask calculates distance and ETA
7. arrival is recorded when the user is within 100 metres of the destination

### C. Safety & Risk
The supplied project specification defines:
- Route deviation = +25
- Long stoppage = +20
- Major delay = +20

Status:
- 0–24 = Normal
- 25–49 = Attention Needed
- 50+ = High Risk

The project intentionally uses a transparent rule-based engine instead of machine learning.

### D. Alert & Emergency
The application records:
- Safe Arrival
- Delay
- High Risk
- SOS

The supplied specification also mentions SMS as a backup when internet is unavailable. The code provides an extension point for Twilio, but the default project does not require paid/external credentials.

## 5. Database explained

### users
One row represents one registered user.

### journeys
Stores destination, journey status, current GPS position, ETA, risk score and risk flags.

### journey_points
Stores location samples received from the browser.

### alerts
Stores important events and their intended recipient.

## 6. How a journey works

1. Login.
2. Open Dashboard.
3. Enter destination.
4. Click Start Journey.
5. Allow browser location access.
6. JavaScript reads latitude/longitude.
7. Flask receives the coordinates.
8. Haversine distance is calculated.
9. ETA is estimated using a simple average-speed assumption.
10. Risk score is calculated from the active flags.
11. If distance is <= 100 metres, the journey is marked as arrived.
12. Safe Arrival is recorded.

## 7. Why Haversine distance?

Latitude and longitude describe positions on Earth. The Haversine formula gives the approximate straight-line distance between two geographic coordinates.

This mini-project uses it because it is simple enough for a fresher to understand.

Important limitation: it is NOT a road-routing engine. A production application should use a proper maps/routing service for road distance and realistic ETA.

## 8. Why browser GPS?

The browser can request the device's location using the Geolocation API. This keeps the project simple and avoids building a native Android/iOS application.

GPS permission must be granted by the user.

## 9. Risk demo buttons

The dashboard includes demo controls:
- Toggle Route Deviation
- Toggle Long Stoppage
- Toggle Major Delay
- Clear Risk

These are for college demonstrations. They make it possible to show all three risk states without intentionally creating unsafe travel situations.

Examples:
- no flags → 0 → Normal
- route deviation → 25 → Attention Needed
- route deviation + long stoppage + major delay → 65 → High Risk

## 10. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/profile` | Update profile |
| POST | `/api/journey/start` | Start journey |
| GET | `/api/journey/status` | Read active journey |
| POST | `/api/journey/update` | Send GPS point and calculate ETA/risk |
| POST | `/api/journey/demo-risk` | Demonstrate risk rules |
| POST | `/api/journey/sos` | Record SOS |
| POST | `/api/journey/stop` | Stop active journey |

## 11. Installation

### Windows

Open the project folder in VS Code.

Terminal:

```text
python -m venv venv
```

Activate:

```text
venv\Scripts\activate
```

Install:

```text
pip install -r requirements.txt
```

Run:

```text
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 12. First test

1. Register.
2. Login.
3. Open Profile and check trusted contact.
4. Open Dashboard.
5. Enter any destination name and coordinates.
6. Click Start Journey.
7. Confirm Journey shows Started.
8. Use demo risk buttons.
9. Confirm the score changes.
10. Trigger SOS.
11. Open History.
12. Confirm the journey/alerts appear.

## 13. Example demonstration

A simple viva demonstration can be:

### Demo 1 — Journey not started
Dashboard shows:
`Not Started`

### Demo 2 — Start journey
Enter destination and coordinates.
Dashboard shows:
`Started`

### Demo 3 — Normal
No risk flags.
Score = 0.
Status = Normal.

### Demo 4 — Attention Needed
Toggle Route Deviation.
Score = 25.
Status = Attention Needed.

### Demo 5 — High Risk
Keep Route Deviation active and enable Long Stoppage and Major Delay.
Score = 65.
Status = High Risk.
An alert record is created.

### Demo 6 — SOS
Press SOS.
An SOS event is recorded.

### Demo 7 — History
Open History to show recorded journeys and alerts.

## 14. Limitations

This is a college mini-project, not a certified emergency service.

Current limitations:
- ETA is a simple estimate based on straight-line distance and assumed speed.
- Route deviation is demonstrated with a rule flag rather than a real map route comparison.
- Long stoppage and major delay are rule flags/demo controls.
- SMS requires an external provider and credentials.
- Browser GPS depends on device/browser permission.
- SQLite is suitable for a student project but not ideal for large-scale production.

## 15. Future enhancements

Possible future improvements:
- live map display
- road-aware routing and ETA
- real route-deviation detection
- background mobile GPS
- Firebase push notifications
- Twilio SMS backup
- multilingual UI
- AI-based risk analysis
- wearable integration
- stronger authentication and deployment security

## 16. Viva questions and simple answers

**Q: Why Flask?**
A: Flask is lightweight, beginner-friendly and suitable for connecting HTML/JavaScript with Python backend logic.

**Q: Why SQLite?**
A: It is simple, file-based and does not require installing a separate database server.

**Q: What is ETA?**
A: Estimated Time of Arrival, meaning the estimated remaining time before reaching the destination.

**Q: What is the risk score?**
A: A simple numeric score formed by adding points for detected journey conditions.

**Q: Why is 50 High Risk?**
A: The project specification defines 50+ as High Risk.

**Q: What is an API?**
A: An interface through which the frontend and backend exchange data.

**Q: What does JavaScript do here?**
A: It handles dashboard interactions, browser GPS and calls the Flask APIs.

**Q: Is this AI?**
A: The supplied design uses a simple rule-based risk score. AI is listed as a possible future enhancement, not required for the core version.

## 17. Folder explanation

```text
app.py                 → Python backend
requirements.txt       → Python dependencies
.env.example           → optional SMS configuration template
README.md              → installation and usage
templates/             → HTML pages
static/style.css       → website styling
static/app.js          → frontend logic and GPS/API calls
safety_arrival.db      → created automatically when the app runs
```

## 18. Source alignment

The implementation follows the supplied project document's module structure:
Login & Profile → Journey & Tracking → Safety & Risk → Alert & Emergency → Database/Offline support.

Where the supplied document is high-level, this implementation makes a simple, clearly labeled student-project choice rather than claiming production-grade behavior.
