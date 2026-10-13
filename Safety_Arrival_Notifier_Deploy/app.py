import os
import math
import re
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Set SECRET_KEY in Render's Environment settings before deployment.
# This fallback is only for local development.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "local-development-only-key"
)

# DATABASE_PATH can point to persistent storage if configured later.
DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "safety_arrival.db")
)

# Demo-only admin password recovery code.
# For a real deployment, use a secure one-time recovery mechanism.
ADMIN_RECOVERY_CODE = os.environ.get("ADMIN_RECOVERY_CODE", "")


# =========================================================
# DATABASE
# =========================================================

def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


def table_columns(conn, table_name):

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def now_iso():

    return datetime.now(
        timezone.utc
    ).isoformat()


# =========================================================
# PHONE VALIDATION
# =========================================================

def is_valid_phone(phone):

    """
    Phone number must contain exactly
    10 digits.

    Examples:
    9876543210  -> valid
    12345       -> invalid
    +919876543210 -> invalid
    98765abc10  -> invalid
    """

    return bool(
        re.fullmatch(
            r"[0-9]{10}",
            phone
        )
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            trusted_name TEXT,
            trusted_phone TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            destination_name TEXT NOT NULL,
            destination_lat REAL NOT NULL,
            destination_lng REAL NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL DEFAULT 'started',
            current_lat REAL,
            current_lng REAL,
            eta_minutes REAL,
            risk_score INTEGER NOT NULL DEFAULT 0,
            risk_status TEXT NOT NULL DEFAULT 'Normal',
            route_deviation INTEGER NOT NULL DEFAULT 0,
            long_stoppage INTEGER NOT NULL DEFAULT 0,
            major_delay INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS journey_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journey_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            recorded_at TEXT NOT NULL,

            FOREIGN KEY (journey_id)
                REFERENCES journeys(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            journey_id INTEGER,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            recipient TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (journey_id)
                REFERENCES journeys(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS trusted_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            contact_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(user_id, contact_number),

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    # =====================================================
    # ALERT DATABASE UPGRADE
    # =====================================================

    alert_columns = table_columns(
        conn,
        "alerts"
    )

    if "recipient_phone" not in alert_columns:

        conn.execute(
            """
            ALTER TABLE alerts
            ADD COLUMN recipient_phone TEXT
            """
        )

    # =====================================================
    # JOURNEY DATABASE UPGRADES
    # =====================================================

    journey_columns = table_columns(
        conn,
        "journeys"
    )

    if "current_lat" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN current_lat REAL
            """
        )

    if "current_lng" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN current_lng REAL
            """
        )

    if "eta_minutes" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN eta_minutes REAL
            """
        )

    if "risk_score" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN risk_score INTEGER
            NOT NULL DEFAULT 0
            """
        )

    if "risk_status" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN risk_status TEXT
            NOT NULL DEFAULT 'Normal'
            """
        )

    if "route_deviation" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN route_deviation INTEGER
            NOT NULL DEFAULT 0
            """
        )

    if "long_stoppage" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN long_stoppage INTEGER
            NOT NULL DEFAULT 0
            """
        )

    if "major_delay" not in journey_columns:

        conn.execute(
            """
            ALTER TABLE journeys
            ADD COLUMN major_delay INTEGER
            NOT NULL DEFAULT 0
            """
        )

    # =====================================================
    # MIGRATE OLD SINGLE TRUSTED CONTACT
    # =====================================================

    users = conn.execute(
        """
        SELECT
            id,
            trusted_name,
            trusted_phone
        FROM users
        WHERE trusted_name IS NOT NULL
        AND trusted_name != ''
        AND trusted_phone IS NOT NULL
        AND trusted_phone != ''
        """
    ).fetchall()

    for user in users:

        existing = conn.execute(
            """
            SELECT id
            FROM trusted_contacts
            WHERE user_id=?
            AND contact_number=1
            """,
            (
                user["id"],
            )
        ).fetchone()

        if not existing:

            conn.execute(
                """
                INSERT INTO trusted_contacts(
                    user_id,
                    contact_number,
                    name,
                    phone,
                    created_at,
                    updated_at
                )
                VALUES (?, 1, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    user["trusted_name"],
                    user["trusted_phone"],
                    now_iso(),
                    now_iso()
                )
            )

    # =====================================================
    # CREATE DEMO ADMIN
    # =====================================================

    # Create an administrator only when credentials are explicitly
    # configured in the environment. Do not ship a public default password.
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if admin_email and admin_password:
        admin_exists = conn.execute(
            "SELECT id FROM admins WHERE email=?",
            (admin_email,)
        ).fetchone()

        if not admin_exists:
            conn.execute(
                """
                INSERT INTO admins(name, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "System Administrator",
                    admin_email,
                    generate_password_hash(admin_password),
                    now_iso()
                )
            )

    conn.commit()

    conn.close()


# =========================================================
# LOGIN PROTECTION
# =========================================================

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "admin_id" not in session:

            return redirect(
                url_for("admin_login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# =========================================================
# GPS + RISK
# =========================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    radius = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(
        lat2 - lat1
    )

    dl = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return (
        2
        * radius
        * math.asin(
            math.sqrt(a)
        )
    )


def calculate_risk(
    route_deviation,
    long_stoppage,
    major_delay
):

    score = 0

    if route_deviation:
        score += 25

    if long_stoppage:
        score += 20

    if major_delay:
        score += 20

    if score >= 50:

        status = "High Risk"

    elif score >= 25:

        status = "Attention Needed"

    else:

        status = "Normal"

    return score, status


def estimate_eta_minutes(
    distance_km,
    speed_kmh=30
):

    if distance_km <= 0:

        return 0

    return round(
        (
            distance_km
            /
            max(speed_kmh, 1)
        )
        * 60,
        1
    )


# =========================================================
# TRUSTED CONTACT HELPERS
# =========================================================

def get_trusted_contacts(
    conn,
    user_id
):

    rows = conn.execute(
        """
        SELECT
            id,
            contact_number,
            name,
            phone
        FROM trusted_contacts
        WHERE user_id=?
        ORDER BY contact_number
        """,
        (
            user_id,
        )
    ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def create_alert_for_contact(
    conn,
    user_id,
    journey_id,
    alert_type,
    message,
    contact_name,
    contact_phone
):

    conn.execute(
        """
        INSERT INTO alerts(
            user_id,
            journey_id,
            alert_type,
            message,
            recipient,
            recipient_phone,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            journey_id,
            alert_type,
            message,
            contact_name,
            contact_phone,
            now_iso()
        )
    )


def create_alerts_for_contacts(
    conn,
    user_id,
    journey_id,
    alert_type,
    message
):

    contacts = get_trusted_contacts(
        conn,
        user_id
    )

    if not contacts:

        create_alert_for_contact(
            conn,
            user_id,
            journey_id,
            alert_type,
            message,
            "No trusted contact saved",
            ""
        )

        return

    for contact in contacts:

        create_alert_for_contact(
            conn,
            user_id,
            journey_id,
            alert_type,
            message,
            contact["name"],
            contact["phone"]
        )


def get_active_journey(
    conn,
    user_id
):

    return conn.execute(
        """
        SELECT *
        FROM journeys
        WHERE user_id=?
        AND status='started'
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            user_id,
        )
    ).fetchone()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        trusted_name = request.form.get(
            "trusted_name",
            ""
        ).strip()

        trusted_phone = request.form.get(
            "trusted_phone",
            ""
        ).strip()

        # -------------------------------------------------
        # REQUIRED FIELDS
        # -------------------------------------------------

        if not name or not email or not password:

            return render_template(
                "register.html",
                error=(
                    "Name, email and password "
                    "are required."
                )
            )

        # -------------------------------------------------
        # USER PHONE VALIDATION
        # -------------------------------------------------

        if phone and not is_valid_phone(phone):

            return render_template(
                "register.html",
                error=(
                    "Your phone number must "
                    "contain exactly 10 digits."
                )
            )

        # -------------------------------------------------
        # TRUSTED CONTACT VALIDATION
        # -------------------------------------------------

        if trusted_name and not trusted_phone:

            return render_template(
                "register.html",
                error=(
                    "Trusted contact phone "
                    "number is required."
                )
            )

        if trusted_phone and not trusted_name:

            return render_template(
                "register.html",
                error=(
                    "Trusted contact name "
                    "is required."
                )
            )

        if trusted_phone and not is_valid_phone(
            trusted_phone
        ):

            return render_template(
                "register.html",
                error=(
                    "Trusted contact phone "
                    "number must contain "
                    "exactly 10 digits."
                )
            )

        conn = get_db()

        try:

            cursor = conn.execute(
                """
                INSERT INTO users(
                    name,
                    email,
                    password_hash,
                    phone,
                    trusted_name,
                    trusted_phone,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(
                        password
                    ),
                    phone,
                    trusted_name,
                    trusted_phone,
                    now_iso()
                )
            )

            user_id = cursor.lastrowid

            if trusted_name and trusted_phone:

                conn.execute(
                    """
                    INSERT INTO trusted_contacts(
                        user_id,
                        contact_number,
                        name,
                        phone,
                        created_at,
                        updated_at
                    )
                    VALUES (?, 1, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        trusted_name,
                        trusted_phone,
                        now_iso(),
                        now_iso()
                    )
                )

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                error=(
                    "This email is already "
                    "registered."
                )
            )

        conn.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# USER LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (
                email,
            )
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error=(
                "Invalid email or password."
            )
        )

    return render_template(
        "login.html"
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        new_password = request.form.get(
            "password",
            ""
        )

        if (
            not email
            or not phone
            or not new_password
        ):

            return render_template(
                "forgot_password.html",
                error=(
                    "Email, phone number and "
                    "new password are required."
                )
            )

        if not is_valid_phone(phone):

            return render_template(
                "forgot_password.html",
                error=(
                    "Phone number must contain "
                    "exactly 10 digits."
                )
            )

        if len(new_password) < 6:

            return render_template(
                "forgot_password.html",
                error=(
                    "New password must contain "
                    "at least 6 characters."
                )
            )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            AND phone=?
            """,
            (
                email,
                phone
            )
        ).fetchone()

        if not user:

            conn.close()

            return render_template(
                "forgot_password.html",
                error=(
                    "Email and phone number "
                    "do not match our records."
                )
            )

        conn.execute(
            """
            UPDATE users
            SET password_hash=?
            WHERE id=?
            """,
            (
                generate_password_hash(
                    new_password
                ),
                user["id"]
            )
        )

        conn.commit()
        conn.close()

        return render_template(
            "forgot_password.html",
            success=(
                "Password reset successfully. "
                "You can now login with your "
                "new password."
            )
        )

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# =========================================================
# USER PAGES
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    return render_template(
        "dashboard.html"
    )


@app.route("/profile")
@login_required
def profile():

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id=?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    contacts = get_trusted_contacts(
        conn,
        session["user_id"]
    )

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        contacts=contacts
    )


@app.route("/history")
@login_required
def history():

    conn = get_db()

    journeys = conn.execute(
        """
        SELECT *
        FROM journeys
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (
            session["user_id"],
        )
    ).fetchall()

    alerts = conn.execute(
        """
        SELECT *
        FROM alerts
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 100
        """,
        (
            session["user_id"],
        )
    ).fetchall()

    conn.close()

    return render_template(
        "history.html",
        journeys=journeys,
        alerts=alerts
    )


# =========================================================
# PROFILE API
# =========================================================

@app.route(
    "/api/profile",
    methods=["POST"]
)
@login_required
def update_profile():

    data = request.get_json(
        silent=True
    ) or {}

    name = data.get(
        "name",
        ""
    ).strip()

    # =====================================================
    # NEW: EMAIL FROM PROFILE
    # =====================================================

    email = data.get(
        "email",
        ""
    ).strip().lower()

    phone = data.get(
        "phone",
        ""
    ).strip()

    contacts = data.get(
        "contacts",
        []
    )

    # -----------------------------------------------------
    # NAME
    # -----------------------------------------------------

    if not name:

        return jsonify({
            "ok": False,
            "message": "Name is required."
        }), 400

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    if not email:

        return jsonify({
            "ok": False,
            "message": "Email is required."
        }), 400

    # -----------------------------------------------------
    # CHECK EMAIL FORMAT
    # -----------------------------------------------------

    email_pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if not re.fullmatch(
        email_pattern,
        email
    ):

        return jsonify({
            "ok": False,
            "message": "Please enter a valid email address."
        }), 400

    # -----------------------------------------------------
    # USER PHONE
    # -----------------------------------------------------

    if phone and not is_valid_phone(phone):

        return jsonify({
            "ok": False,
            "message": (
                "Your phone number must "
                "contain exactly 10 digits."
            )
        }), 400

    # -----------------------------------------------------
    # CONTACT LIST
    # -----------------------------------------------------

    if not isinstance(
        contacts,
        list
    ):

        return jsonify({
            "ok": False,
            "message": (
                "Contacts must be a list."
            )
        }), 400

    if len(contacts) > 4:

        return jsonify({
            "ok": False,
            "message": (
                "You can save up to "
                "4 trusted contacts."
            )
        }), 400

    cleaned_contacts = []

    for index, contact in enumerate(
        contacts,
        start=1
    ):

        if not isinstance(
            contact,
            dict
        ):

            return jsonify({
                "ok": False,
                "message": (
                    f"Contact {index} "
                    "is invalid."
                )
            }), 400

        contact_name = str(
            contact.get(
                "name",
                ""
            )
        ).strip()

        contact_phone = str(
            contact.get(
                "phone",
                ""
            )
        ).strip()

        # Empty contact slot is allowed
        if (
            not contact_name
            and not contact_phone
        ):

            continue

        # Half-filled contact
        if (
            not contact_name
            or not contact_phone
        ):

            return jsonify({
                "ok": False,
                "message": (
                    f"Contact {index} needs "
                    "both name and phone number."
                )
            }), 400

        # 10 digit validation
        if not is_valid_phone(
            contact_phone
        ):

            return jsonify({
                "ok": False,
                "message": (
                    f"Contact {index} phone "
                    "number must contain "
                    "exactly 10 digits."
                )
            }), 400

        cleaned_contacts.append(
            (
                len(cleaned_contacts) + 1,
                contact_name,
                contact_phone
            )
        )

    conn = get_db()

    # =====================================================
    # NEW: CHECK IF EMAIL BELONGS TO ANOTHER USER
    # =====================================================

    existing_email = conn.execute(
        """
        SELECT id
        FROM users
        WHERE email=?
        AND id !=?
        """,
        (
            email,
            session["user_id"]
        )
    ).fetchone()

    if existing_email:

        conn.close()

        return jsonify({
            "ok": False,
            "message": (
                "This email is already "
                "used by another account."
            )
        }), 400

    # =====================================================
    # UPDATE USER PROFILE
    # =====================================================

    conn.execute(
        """
        UPDATE users
        SET name=?,
            email=?,
            phone=?
        WHERE id=?
        """,
        (
            name,
            email,
            phone,
            session["user_id"]
        )
    )

    # =====================================================
    # DELETE OLD CONTACTS
    # =====================================================

    conn.execute(
        """
        DELETE FROM trusted_contacts
        WHERE user_id=?
        """,
        (
            session["user_id"],
        )
    )

    # =====================================================
    # SAVE NEW CONTACTS
    # =====================================================

    for (
        contact_number,
        contact_name,
        contact_phone
    ) in cleaned_contacts:

        conn.execute(
            """
            INSERT INTO trusted_contacts(
                user_id,
                contact_number,
                name,
                phone,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                contact_number,
                contact_name,
                contact_phone,
                now_iso(),
                now_iso()
            )
        )

    # =====================================================
    # KEEP OLD TRUSTED CONTACT FIELDS SYNCHRONIZED
    # =====================================================

    first_contact = (
        cleaned_contacts[0]
        if cleaned_contacts
        else None
    )

    if first_contact:

        conn.execute(
            """
            UPDATE users
            SET trusted_name=?,
                trusted_phone=?
            WHERE id=?
            """,
            (
                first_contact[1],
                first_contact[2],
                session["user_id"]
            )
        )

    else:

        conn.execute(
            """
            UPDATE users
            SET trusted_name=NULL,
                trusted_phone=NULL
            WHERE id=?
            """,
            (
                session["user_id"],
            )
        )

    conn.commit()
    conn.close()

    # =====================================================
    # UPDATE SESSION
    # =====================================================

    session["user_name"] = name
    session["user_email"] = email

    return jsonify({
        "ok": True,
        "message": (
            "Profile and trusted contacts "
            "updated successfully."
        ),
        "email": email,
        "contacts": [
            {
                "contact_number": number,
                "name": contact_name,
                "phone": contact_phone
            }
            for (
                number,
                contact_name,
                contact_phone
            ) in cleaned_contacts
        ]
    })


# =========================================================
# CONTACTS API
# =========================================================

@app.route("/api/contacts")
@login_required
def contacts_api():

    conn = get_db()

    contacts = get_trusted_contacts(
        conn,
        session["user_id"]
    )

    conn.close()

    return jsonify({
        "ok": True,
        "contacts": contacts
    })


# =========================================================
# START JOURNEY
# =========================================================

@app.route(
    "/api/journey/start",
    methods=["POST"]
)
@login_required
def start_journey():

    data = request.get_json(
        silent=True
    ) or {}

    destination_name = data.get(
        "destination_name",
        ""
    ).strip()

    destination_lat = data.get(
        "destination_lat"
    )

    destination_lng = data.get(
        "destination_lng"
    )

    if (
        not destination_name
        or destination_lat is None
        or destination_lng is None
    ):

        return jsonify({
            "ok": False,
            "message": (
                "Destination name and "
                "coordinates are required."
            )
        }), 400

    try:

        destination_lat = float(
            destination_lat
        )

        destination_lng = float(
            destination_lng
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "ok": False,
            "message": (
                "Destination coordinates "
                "are invalid."
            )
        }), 400

    if not -90 <= destination_lat <= 90:

        return jsonify({
            "ok": False,
            "message": (
                "Invalid destination latitude."
            )
        }), 400

    if not -180 <= destination_lng <= 180:

        return jsonify({
            "ok": False,
            "message": (
                "Invalid destination longitude."
            )
        }), 400

    conn = get_db()

    active = get_active_journey(
        conn,
        session["user_id"]
    )

    if active:

        conn.close()

        return jsonify({
            "ok": False,
            "message": (
                "A journey is already running."
            )
        }), 400

    cursor = conn.execute(
        """
        INSERT INTO journeys(
            user_id,
            destination_name,
            destination_lat,
            destination_lng,
            started_at,
            status,
            risk_score,
            risk_status
        )
        VALUES (?, ?, ?, ?, ?, 'started', 0, 'Normal')
        """,
        (
            session["user_id"],
            destination_name,
            destination_lat,
            destination_lng,
            now_iso()
        )
    )

    journey_id = cursor.lastrowid

    create_alerts_for_contacts(
        conn,
        session["user_id"],
        journey_id,
        "Journey Started",
        (
            f"Journey to {destination_name} "
            "has started. Live safety "
            "monitoring is active."
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "journey_id": journey_id,
        "message": "Journey started."
    })


# =========================================================
# JOURNEY STATUS
# =========================================================

@app.route(
    "/api/journey/status"
)
@login_required
def journey_status():

    conn = get_db()

    journey = get_active_journey(
        conn,
        session["user_id"]
    )

    contacts = get_trusted_contacts(
        conn,
        session["user_id"]
    )

    if not journey:

        conn.close()

        return jsonify({
            "active": False,
            "contacts": contacts
        })

    payload = dict(journey)

    payload["contacts"] = contacts
    payload["active"] = True

    if (
        journey["current_lat"] is not None
        and journey["current_lng"] is not None
    ):

        distance_km = haversine_km(
            journey["current_lat"],
            journey["current_lng"],
            journey["destination_lat"],
            journey["destination_lng"]
        )

        payload["distance_km"] = round(
            distance_km,
            3
        )

        payload["near_destination"] = (
            distance_km <= 1.0
        )

    else:

        payload["distance_km"] = None
        payload["near_destination"] = False

    conn.close()

    return jsonify(payload)


# =========================================================
# UPDATE JOURNEY GPS
# =========================================================

@app.route(
    "/api/journey/update",
    methods=["POST"]
)
@login_required
def update_journey():

    data = request.get_json(
        silent=True
    ) or {}

    latitude = data.get(
        "latitude"
    )

    longitude = data.get(
        "longitude"
    )

    try:

        latitude = float(latitude)
        longitude = float(longitude)

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "ok": False,
            "message": (
                "Latitude and longitude "
                "are required."
            )
        }), 400

    if not -90 <= latitude <= 90:

        return jsonify({
            "ok": False,
            "message": "Invalid latitude."
        }), 400

    if not -180 <= longitude <= 180:

        return jsonify({
            "ok": False,
            "message": "Invalid longitude."
        }), 400

    conn = get_db()

    journey = get_active_journey(
        conn,
        session["user_id"]
    )

    if not journey:

        conn.close()

        return jsonify({
            "ok": False,
            "message": "No active journey."
        }), 404

    distance_km = haversine_km(
        latitude,
        longitude,
        journey["destination_lat"],
        journey["destination_lng"]
    )

    eta = estimate_eta_minutes(
        distance_km
    )

    score, risk_status = calculate_risk(
        journey["route_deviation"],
        journey["long_stoppage"],
        journey["major_delay"]
    )

    conn.execute(
        """
        UPDATE journeys
        SET current_lat=?,
            current_lng=?,
            eta_minutes=?,
            risk_score=?,
            risk_status=?
        WHERE id=?
        """,
        (
            latitude,
            longitude,
            eta,
            score,
            risk_status,
            journey["id"]
        )
    )

    conn.execute(
        """
        INSERT INTO journey_points(
            journey_id,
            latitude,
            longitude,
            recorded_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            journey["id"],
            latitude,
            longitude,
            now_iso()
        )
    )

    # -----------------------------------------------------
    # NEAR DESTINATION = 1 KM
    # -----------------------------------------------------

    near_destination = (
        distance_km <= 1.0
    )

    # -----------------------------------------------------
    # SAFE ARRIVAL = 200 METRES
    # -----------------------------------------------------

    if distance_km <= 0.2:

        conn.execute(
            """
            UPDATE journeys
            SET status='arrived',
                ended_at=?,
                eta_minutes=0,
                risk_score=0,
                risk_status='Normal'
            WHERE id=?
            """,
            (
                now_iso(),
                journey["id"]
            )
        )

        existing_arrival = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE journey_id=?
            AND alert_type='Safe Arrival'
            LIMIT 1
            """,
            (
                journey["id"],
            )
        ).fetchone()

        if not existing_arrival:

            create_alerts_for_contacts(
                conn,
                session["user_id"],
                journey["id"],
                "Safe Arrival",
                (
                    f"Safe arrival detected at "
                    f"{journey['destination_name']}."
                )
            )

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "arrived": True,
            "near_destination": True,
            "distance_km": round(
                distance_km,
                3
            ),
            "eta_minutes": 0,
            "risk_score": 0,
            "risk_status": "Normal",
            "message": (
                "Destination reached. "
                "Safe arrival recorded."
            )
        })

    # -----------------------------------------------------
    # HIGH RISK
    # -----------------------------------------------------

    if risk_status == "High Risk":

        existing_high_risk = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE journey_id=?
            AND alert_type='High Risk'
            LIMIT 1
            """,
            (
                journey["id"],
            )
        ).fetchone()

        if not existing_high_risk:

            create_alerts_for_contacts(
                conn,
                session["user_id"],
                journey["id"],
                "High Risk",
                (
                    "High-risk journey condition "
                    "detected. Trusted contact "
                    "should be alerted."
                )
            )

    # -----------------------------------------------------
    # DELAY
    # -----------------------------------------------------

    if eta >= 60:

        existing_delay = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE journey_id=?
            AND alert_type='Delay'
            LIMIT 1
            """,
            (
                journey["id"],
            )
        ).fetchone()

        if not existing_delay:

            create_alerts_for_contacts(
                conn,
                session["user_id"],
                journey["id"],
                "Delay",
                (
                    f"Journey is estimated to "
                    f"take about {eta} minutes "
                    "from the current position."
                )
            )

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "arrived": False,
        "near_destination": near_destination,
        "distance_km": round(
            distance_km,
            3
        ),
        "eta_minutes": eta,
        "risk_score": score,
        "risk_status": risk_status
    })


# =========================================================
# DEMO RISK
# =========================================================

@app.route(
    "/api/demo/risk",
    methods=["POST"]
)
@app.route(
    "/api/journey/demo-risk",
    methods=["POST"]
)
@login_required
def demo_risk():

    data = request.get_json(
        silent=True
    ) or {}

    condition = data.get(
        "condition"
    )

    conn = get_db()

    journey = get_active_journey(
        conn,
        session["user_id"]
    )

    if not journey:

        conn.close()

        return jsonify({
            "ok": False,
            "message": "Start a journey first."
        }), 400

    flags = {
        "route_deviation":
            journey["route_deviation"],

        "long_stoppage":
            journey["long_stoppage"],

        "major_delay":
            journey["major_delay"]
    }

    if condition in flags:

        flags[condition] = (
            0
            if flags[condition]
            else 1
        )

    elif condition == "clear":

        flags = {
            key: 0
            for key in flags
        }

    else:

        conn.close()

        return jsonify({
            "ok": False,
            "message": (
                "Unknown demo condition."
            )
        }), 400

    score, status = calculate_risk(
        **flags
    )

    conn.execute(
        """
        UPDATE journeys
        SET route_deviation=?,
            long_stoppage=?,
            major_delay=?,
            risk_score=?,
            risk_status=?
        WHERE id=?
        """,
        (
            flags["route_deviation"],
            flags["long_stoppage"],
            flags["major_delay"],
            score,
            status,
            journey["id"]
        )
    )

    # -----------------------------------------------------
    # HIGH RISK ALERT
    # -----------------------------------------------------

    if status == "High Risk":

        existing = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE journey_id=?
            AND alert_type='High Risk'
            LIMIT 1
            """,
            (
                journey["id"],
            )
        ).fetchone()

        if not existing:

            create_alerts_for_contacts(
                conn,
                session["user_id"],
                journey["id"],
                "High Risk",
                (
                    "High-risk condition triggered "
                    "by the safety risk engine."
                )
            )

    # -----------------------------------------------------
    # ATTENTION ALERT
    # -----------------------------------------------------

    elif status == "Attention Needed":

        existing = conn.execute(
            """
            SELECT id
            FROM alerts
            WHERE journey_id=?
            AND alert_type='Attention Needed'
            LIMIT 1
            """,
            (
                journey["id"],
            )
        ).fetchone()

        if not existing:

            create_alerts_for_contacts(
                conn,
                session["user_id"],
                journey["id"],
                "Attention Needed",
                (
                    "An attention-needed condition "
                    "was detected by the safety "
                    "risk engine."
                )
            )

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "risk_score": score,
        "risk_status": status,
        "flags": flags
    })


# =========================================================
# SOS
# =========================================================

@app.route(
    "/api/journey/sos",
    methods=["POST"]
)
@login_required
def sos():

    conn = get_db()

    journey = get_active_journey(
        conn,
        session["user_id"]
    )

    if journey:

        journey_id = journey["id"]

        message = (
            "SOS alert triggered by the user "
            "during an active journey."
        )

    else:

        journey_id = None

        message = (
            "SOS alert triggered by the user."
        )

    create_alerts_for_contacts(
        conn,
        session["user_id"],
        journey_id,
        "SOS",
        message
    )

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "message": (
            "SOS recorded for the saved "
            "trusted contacts. In a production "
            "version, this event could also be "
            "sent through an SMS or emergency "
            "notification provider."
        )
    })


# =========================================================
# STOP JOURNEY
# =========================================================

@app.route(
    "/api/journey/stop",
    methods=["POST"]
)
@login_required
def stop_journey():

    conn = get_db()

    journey = get_active_journey(
        conn,
        session["user_id"]
    )

    if not journey:

        conn.close()

        return jsonify({
            "ok": False,
            "message": "No active journey."
        }), 404

    conn.execute(
        """
        UPDATE journeys
        SET status='stopped',
            ended_at=?
        WHERE id=?
        """,
        (
            now_iso(),
            journey["id"]
        )
    )

    create_alerts_for_contacts(
        conn,
        session["user_id"],
        journey["id"],
        "Journey Stopped",
        (
            f"Journey to "
            f"{journey['destination_name']} "
            "has been stopped."
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "message": "Journey stopped."
    })


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE email=?
            """,
            (
                email,
            )
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password_hash"],
            password
        ):

            session.clear()

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]

            return redirect(
                url_for("admin_dashboard")
            )

        return render_template(
            "admin_login.html",
            error=(
                "Invalid admin email "
                "or password."
            )
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN FORGOT / RESET PASSWORD
# =========================================================

@app.route(
    "/admin/forgot-password",
    methods=["GET", "POST"]
)
def admin_forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        recovery_code = request.form.get(
            "recovery_code",
            ""
        ).strip()

        new_password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if (
            not email
            or not recovery_code
            or not new_password
            or not confirm_password
        ):
            return render_template(
                "admin_forgot_password.html",
                error="All fields are required."
            )

        if len(new_password) < 6:
            return render_template(
                "admin_forgot_password.html",
                error=(
                    "New password must contain "
                    "at least 6 characters."
                )
            )

        if new_password != confirm_password:
            return render_template(
                "admin_forgot_password.html",
                error=(
                    "New password and confirm "
                    "password do not match."
                )
            )

        if not ADMIN_RECOVERY_CODE or recovery_code != ADMIN_RECOVERY_CODE:
            return render_template(
                "admin_forgot_password.html",
                error="Invalid admin recovery code."
            )

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE email=?
            """,
            (email,)
        ).fetchone()

        if not admin:
            conn.close()
            return render_template(
                "admin_forgot_password.html",
                error=(
                    "No admin account was found "
                    "with this email address."
                )
            )

        conn.execute(
            """
            UPDATE admins
            SET password_hash=?
            WHERE id=?
            """,
            (
                generate_password_hash(new_password),
                admin["id"]
            )
        )

        conn.commit()
        conn.close()

        return render_template(
            "admin_forgot_password.html",
            success=(
                "Admin password reset successfully. "
                "You can now login with your new password."
            )
        )

    return render_template(
        "admin_forgot_password.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    conn = get_db()

    total_users = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        """
    ).fetchone()["count"]

    active_journeys = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM journeys
        WHERE status='started'
        """
    ).fetchone()["count"]

    total_journeys = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM journeys
        """
    ).fetchone()["count"]

    total_alerts = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM alerts
        """
    ).fetchone()["count"]

    high_risk_alerts = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM alerts
        WHERE alert_type='High Risk'
        """
    ).fetchone()["count"]

    sos_alerts = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM alerts
        WHERE alert_type='SOS'
        """
    ).fetchone()["count"]

    users = conn.execute(
        """
        SELECT
            id,
            name,
            email,
            phone,
            created_at
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    contacts = conn.execute(
        """
        SELECT
            tc.id,
            tc.contact_number,
            tc.name,
            tc.phone,
            u.name AS user_name,
            u.email AS user_email
        FROM trusted_contacts tc
        JOIN users u
            ON tc.user_id = u.id
        ORDER BY tc.id DESC
        """
    ).fetchall()

    journeys = conn.execute(
        """
        SELECT
            j.*,
            u.name AS user_name,
            u.email AS user_email
        FROM journeys j
        JOIN users u
            ON j.user_id = u.id
        ORDER BY j.id DESC
        """
    ).fetchall()

    alerts = conn.execute(
        """
        SELECT
            a.*,
            u.name AS user_name,
            u.email AS user_email
        FROM alerts a
        JOIN users u
            ON a.user_id = u.id
        ORDER BY a.id DESC
        LIMIT 200
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        active_journeys=active_journeys,
        total_journeys=total_journeys,
        total_alerts=total_alerts,
        high_risk_alerts=high_risk_alerts,
        sos_alerts=sos_alerts,
        users=users,
        contacts=contacts,
        journeys=journeys,
        alerts=alerts
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )