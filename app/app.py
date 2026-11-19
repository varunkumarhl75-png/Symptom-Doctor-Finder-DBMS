from datetime import date, datetime, time, timedelta
from functools import wraps
import logging
import os
import re
from urllib.parse import urlsplit
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_wtf.csrf import CSRFProtect
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash
from cache import get_cache_stats, redis_health
from db import get_db_connection
from search_service import get_doctor_groups, get_symptom_match

load_dotenv()
logger = logging.getLogger(__name__)
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is required. Set it in the environment or local .env file."
    )

app = Flask(__name__)
app.config["SECRET_KEY"] = secret_key
app.config["WTF_CSRF_ENABLED"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() == "true"
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8"))
)

csrf = CSRFProtect(app)


class AuthenticationUnavailable(Exception):
    pass


def get_auth_user_by_id(user_id):
    connection = get_db_connection()
    if not connection:
        raise AuthenticationUnavailable

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT
                    u.user_id,
                    u.email,
                    u.role,
                    u.patient_id,
                    p.name AS patient_name,
                    p.phone AS patient_phone
                FROM auth_user u
                LEFT JOIN patient p
                    ON u.patient_id = p.patient_id
                WHERE u.user_id = %s
            """,
            (user_id,)
        )
        return cursor.fetchone()
    except Error as error:
        logger.error(
            "Authenticated-user lookup failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        raise AuthenticationUnavailable from error
    finally:
        cursor.close()
        connection.close()


def get_current_user():
    if getattr(g, "auth_user_loaded", False):
        return g.auth_user

    g.auth_user_loaded = True
    g.auth_user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.auth_user = get_auth_user_by_id(user_id)
        if g.auth_user is None:
            session.clear()
    return g.auth_user


def role_required(*allowed_roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                user = get_current_user()
            except AuthenticationUnavailable:
                return render_template(
                    "index.html",
                    error="Authentication is temporarily unavailable. Please try again.",
                    symptoms=""
                ), 503

            if user is None:
                session.clear()
                next_path = request.full_path.rstrip("?")
                return redirect(url_for("login", next=next_path))
            if user["role"] not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


@app.context_processor
def inject_auth_navigation():
    return {
        "auth_user": {
            "role": session.get("role"),
            "email": session.get("email")
        } if session.get("user_id") else None
    }


def _safe_local_next(candidate):
    if not candidate:
        return None
    parsed = urlsplit(candidate)
    if (
        "\\" in candidate
        or parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
    ):
        return None
    return candidate


def _establish_session(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["role"] = user["role"]
    session["email"] = user["email"]


def get_patient_appointments(connection, patient_id):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.callproc("get_patient_appointments", [patient_id])
        for result in cursor.stored_results():
            return result.fetchall()
        return []
    finally:
        cursor.close()


def get_admin_dashboard_stats(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT
                    (SELECT COUNT(*) FROM patient) AS patient_count,
                    (SELECT COUNT(*) FROM doctor) AS doctor_count,
                    (SELECT COUNT(*) FROM appointment) AS appointment_count,
                    (SELECT COUNT(*)
                     FROM appointment_slot sl
                     WHERE sl.slot_date >= CURRENT_DATE
                       AND NOT EXISTS (
                           SELECT 1
                           FROM appointment a
                           WHERE a.slot_id = sl.slot_id
                             AND a.status <> 'CANCELLED'
                       )) AS available_slot_count
            """
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def get_doctor_details(connection, doctor_id):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT
                    d.doctor_id,
                    d.name AS doctor_name,
                    s.name AS specialization,
                    c.name AS clinic_name,
                    d.qualification,
                    d.experience_years,
                    d.phone
                FROM doctor d
                JOIN specialization s
                    ON d.specialization_id = s.specialization_id
                JOIN clinic c
                    ON d.clinic_id = c.clinic_id
                WHERE d.doctor_id = %s
            """,
            (doctor_id,)
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def get_available_slots(connection, doctor_id, appointment_date):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.callproc("get_doctor_slots", [doctor_id, appointment_date])
        for result in cursor.stored_results():
            return result.fetchall()
        return []
    except Error as error:
        logger.error(
            "Available-slot lookup failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        raise
    finally:
        cursor.close()


def is_slot_in_future(slot_date, slot_start, now=None):
    if isinstance(slot_date, datetime):
        parsed_date = slot_date.date()
    elif isinstance(slot_date, date):
        parsed_date = slot_date
    else:
        parsed_date = date.fromisoformat(str(slot_date))

    if isinstance(slot_start, datetime):
        parsed_time = slot_start.time()
    elif isinstance(slot_start, time):
        parsed_time = slot_start
    else:
        parsed_time = time.fromisoformat(str(slot_start))

    current_time = now or datetime.now()
    return datetime.combine(parsed_date, parsed_time) > current_time


def _mysql_is_healthy():
    connection = get_db_connection()
    if connection is None:
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)
    except Error as error:
        logger.error(
            "MySQL health check failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        return False
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def normalize_patient_phone(phone):
    return re.sub(r"[^0-9]", "", phone)


def cancel_booked_appointment(connection, appointment_id, patient_id):
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """
                SELECT patient_id, status
                FROM appointment
                WHERE appointment_id = %s AND patient_id = %s
                FOR UPDATE
            """,
            (appointment_id, patient_id)
        )
        appointment = cursor.fetchone()
        if not appointment:
            connection.rollback()
            return "NOT_FOUND", None

        patient_id = appointment["patient_id"]
        if appointment["status"] != "BOOKED":
            connection.rollback()
            return appointment["status"], patient_id

        cursor.execute(
            """
                UPDATE appointment
                SET status = 'CANCELLED'
                WHERE appointment_id = %s
                  AND patient_id = %s
                  AND status = 'BOOKED'
            """,
            (appointment_id, patient_id)
        )
        if cursor.rowcount != 1:
            connection.rollback()
            return "NOT_BOOKED", patient_id

        connection.commit()
        return "CANCELLED", patient_id
    except Error:
        connection.rollback()
        raise
    finally:
        cursor.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = " ".join(request.form.get("name", "").split())
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    digits = normalize_patient_phone(phone)
    password = request.form.get("password", "")
    confirmation = request.form.get("confirm_password", "")

    if not name or len(name) > 100:
        return render_template(
            "register.html",
            error="Enter a name up to 100 characters."
        ), 400
    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return render_template("register.html", error="Enter a valid email address."), 400
    if (
        not phone
        or not re.fullmatch(r"[0-9+().\-\s]+", phone)
        or phone.count("+") > 1
        or ("+" in phone and not phone.lstrip().startswith("+"))
        or not 7 <= len(digits) <= 15
    ):
        return render_template("register.html", error="Enter a valid phone number."), 400
    if len(password) < 12 or len(password) > 128:
        return render_template(
            "register.html",
            error="Password must be between 12 and 128 characters."
        ), 400
    if password != confirmation:
        return render_template("register.html", error="Passwords do not match."), 400

    connection = get_db_connection()
    if not connection:
        return render_template(
            "register.html",
            error="Registration is temporarily unavailable. Please try again."
        ), 503

    cursor = connection.cursor()
    try:
        procedure_values = cursor.callproc(
            "register_patient_account",
            [
                name,
                email,
                digits,
                generate_password_hash(password),
                0,
                0
            ]
        )
        user_id = procedure_values[-1]
    except Error as error:
        connection.rollback()
        logger.error(
            "Patient registration failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        duplicate_email = (
            getattr(error, "errno", None) == 1062
            or (
                getattr(error, "errno", None) == 1644
                and "Registration email already exists" in str(error)
            )
        )
        return render_template(
            "register.html",
            error="Registration could not be completed. Check whether this email is already in use."
        ), 409 if duplicate_email else 503
    finally:
        cursor.close()
        connection.close()

    _establish_session({
        "user_id": user_id,
        "role": "PATIENT",
        "email": email
    })
    flash("Your patient account has been created.", "success")
    return redirect(url_for("home"))


@app.route("/login", methods=["GET", "POST"])
def login():
    next_path = _safe_local_next(request.values.get("next"))
    if request.method == "GET":
        return render_template("login.html", next_path=next_path or "")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    connection = get_db_connection()
    if not connection:
        return render_template(
            "login.html",
            next_path=next_path or "",
            error="Login is temporarily unavailable. Please try again."
        ), 503

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT user_id, email, password_hash, role, patient_id
                FROM auth_user
                WHERE email = %s
            """,
            (email,)
        )
        user = cursor.fetchone()
    except Error as error:
        logger.error(
            "Login lookup failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        return render_template(
            "login.html",
            next_path=next_path or "",
            error="Login is temporarily unavailable. Please try again."
        ), 503
    finally:
        cursor.close()
        connection.close()

    try:
        password_matches = (
            user is not None
            and check_password_hash(user["password_hash"], password)
        )
    except (TypeError, ValueError):
        logger.error("Stored password hash is invalid for a login account.")
        password_matches = False

    if not password_matches:
        return render_template(
            "login.html",
            next_path=next_path or "",
            error="Email or password is incorrect."
        ), 401

    _establish_session(user)
    if user["role"] == "ADMIN":
        return redirect(url_for("admin_dashboard"))
    return redirect(next_path or url_for("home"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/api/cache/stats")
def cache_stats():
    return jsonify(get_cache_stats())


@app.route("/api/cache/health")
def cache_health():
    if redis_health():
        return jsonify({"status": "healthy", "redis": "connected"}), 200
    return jsonify({"status": "unhealthy", "redis": "disconnected"}), 503


@app.route("/health")
def application_health():
    mysql_connected = _mysql_is_healthy()
    redis_connected = redis_health()
    healthy = mysql_connected and redis_connected
    return jsonify({
        "status": "healthy" if healthy else "degraded",
        "mysql": "connected" if mysql_connected else "disconnected",
        "redis": "connected" if redis_connected else "disconnected"
    }), 200 if healthy else 503


@app.route("/admin")
@role_required("ADMIN")
def admin_dashboard():
    connection = get_db_connection()
    if not connection:
        return render_template(
            "admin_dashboard.html",
            error="The admin dashboard is temporarily unavailable."
        ), 503
    try:
        stats = get_admin_dashboard_stats(connection)
        return render_template("admin_dashboard.html", stats=stats)
    except Error as error:
        logger.error(
            "Admin dashboard query failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        return render_template(
            "admin_dashboard.html",
            error="The admin dashboard is temporarily unavailable."
        ), 503
    finally:
        connection.close()


@app.route("/search", methods=["POST"])
def search():
    symptoms = request.form.get("symptoms", "").strip()

    if not symptoms:
        return render_template(
            "index.html",
            error="Please describe your symptoms so we can find the right specialist.",
            symptoms=""
        )

    connection = get_db_connection()
    if not connection:
        return render_template(
            "index.html",
            error="We could not connect to the database right now. Please try again in a moment.",
            symptoms=symptoms
        )

    cursor = connection.cursor(dictionary=True)

    try:
        symptom_match = get_symptom_match(cursor, symptoms)
        if symptom_match["status"] == "no_symptoms":
            return render_template(
                "index.html",
                error="No symptom records are available in the system yet.",
                symptoms=symptoms
            )

        if symptom_match["status"] == "no_match":
            return render_template(
                "index.html",
                error="We could not find a strong semantic match for that description. Please try describing your symptoms in a different way.",
                symptoms=symptoms
            )

        search_id = symptom_match["search_id"]
        specialist_groups = get_doctor_groups(cursor, search_id)

        return render_template(
            "results.html",
            symptoms=symptoms,
            matched_symptom=symptom_match["matched_symptom"],
            similarity_score=symptom_match["similarity_score"],
            specialist_groups=specialist_groups,
            search_id=search_id
        )

    except Exception:
        logger.exception("Symptom search failed.")
        return render_template(
            "index.html",
            error="Something went wrong while searching. Please try again.",
            symptoms=symptoms
        )

    finally:
        cursor.close()
        connection.close()


@app.route("/book/<int:doctor_id>", methods=["GET", "POST"])
@role_required("PATIENT")
def book_appointment(doctor_id):
    patient = get_current_user()
    connection = get_db_connection()
    if not connection:
        return render_template(
            "index.html",
            error="Database connection failed. Please try again in a moment.",
            symptoms=""
        )

    try:
        doctor = get_doctor_details(connection, doctor_id)
    except Error as error:
        logger.error(
            "Doctor booking details lookup failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        connection.close()
        return render_template(
            "index.html",
            error="Unable to load booking details right now. Please try again.",
            symptoms=""
        )

    if not doctor:
        connection.close()
        return render_template(
            "index.html",
            error="The selected doctor could not be found.",
            symptoms=""
        )

    selected_date = request.form.get("appointment_date", "").strip() if request.method == "POST" else (
        request.args.get("appointment_date") or request.args.get("date") or ""
    )
    available_slots = []

    def render_booking(error=None):
        connection.close()
        return render_template(
            "book_appointment.html",
            doctor=doctor,
            patient=patient,
            selected_date=selected_date,
            today=date.today().isoformat(),
            available_slots=available_slots,
            error=error
        )

    if request.method == "GET":
        error = None
        if selected_date:
            try:
                parsed_date = date.fromisoformat(selected_date)
            except ValueError:
                error = "Please select a valid appointment date."
            else:
                if parsed_date < date.today():
                    error = "Appointment dates cannot be in the past."
                else:
                    try:
                        available_slots = get_available_slots(
                            connection,
                            doctor_id,
                            selected_date
                        )
                    except Error:
                        error = "Unable to load available slots right now. Please try again."
                    else:
                        available_slots = [
                            slot for slot in available_slots
                            if is_slot_in_future(
                                selected_date,
                                slot["start_time"]
                            )
                        ]
        return render_booking(error)

    if not selected_date:
        return render_booking("Please select an appointment date.")

    try:
        parsed_date = date.fromisoformat(selected_date)
    except ValueError:
        return render_booking("Please select a valid appointment date.")

    if parsed_date < date.today():
        return render_booking("Appointment dates cannot be in the past.")

    slot_id = request.form.get("slot_id", "").strip()
    if not slot_id:
        return render_booking("Please select an available appointment slot.")

    try:
        available_slots = get_available_slots(connection, doctor_id, selected_date)
    except Error:
        return render_booking("Unable to load available slots right now. Please try again.")
    available_slots = [
        slot for slot in available_slots
        if is_slot_in_future(selected_date, slot["start_time"])
    ]
    slot_match = next((slot for slot in available_slots if str(slot["slot_id"]) == slot_id), None)
    if not slot_match:
        return render_booking("This appointment slot is no longer available. Please select another slot.")

    appointment_cursor = connection.cursor()
    booking_error = None
    appointment_id = None
    try:
        connection.commit()
        connection.start_transaction()
        appointment_cursor.execute(
            """
                INSERT INTO appointment (patient_id, slot_id, status, notes)
                VALUES (%s, %s, 'BOOKED', %s)
            """,
            (
                patient["patient_id"],
                slot_id,
                f"Booked via MediFind AI for {doctor['doctor_name']}."
            )
        )
        appointment_id = appointment_cursor.lastrowid
        connection.commit()
    except Error as exc:
        connection.rollback()
        error_message = str(exc).lower()
        if (
            "already occupied" in error_message
            or "already booked" in error_message
            or "already passed" in error_message
            or "uq_appointment_active_slot" in error_message
        ):
            booking_error = "This appointment slot is no longer available. Please select another slot."
        else:
            booking_error = "Appointment could not be created. Please try again."
    finally:
        appointment_cursor.close()

    if booking_error:
        return render_booking(booking_error)

    connection.close()
    return redirect(url_for("appointment_confirmation", appointment_id=appointment_id))


@app.route("/appointment-confirmation/<int:appointment_id>")
@role_required("PATIENT")
def appointment_confirmation(appointment_id):
    patient = get_current_user()
    connection = get_db_connection()
    if not connection:
        return render_template(
            "index.html",
            error="Database connection failed. Please try again in a moment.",
            symptoms=""
        )

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
                SELECT
                    a.appointment_id,
                    a.patient_id,
                    a.status,
                    a.notes,
                    p.name AS patient_name,
                    d.name AS doctor_name,
                    s.name AS specialization,
                    c.name AS clinic_name,
                    sl.slot_date AS appointment_date,
                    sl.start_time,
                    sl.end_time
                FROM appointment a
                JOIN patient p
                    ON a.patient_id = p.patient_id
                JOIN appointment_slot sl
                    ON a.slot_id = sl.slot_id
                JOIN doctor d
                    ON sl.doctor_id = d.doctor_id
                JOIN specialization s
                    ON d.specialization_id = s.specialization_id
                JOIN clinic c
                    ON d.clinic_id = c.clinic_id
                WHERE a.appointment_id = %s
                  AND a.patient_id = %s
            """,
            (appointment_id, patient["patient_id"])
        )
        appointment = cursor.fetchone()
        if not appointment:
            return render_template(
                "index.html",
                error="Appointment details could not be found.",
                symptoms=""
            )
        return render_template("appointment_confirmation.html", appointment=appointment)
    finally:
        cursor.close()
        connection.close()


@app.route("/my-appointments")
@role_required("PATIENT")
def my_appointments():
    patient = get_current_user()
    connection = get_db_connection()
    if not connection:
        return render_template(
            "index.html",
            error="Database connection failed. Please try again in a moment.",
            symptoms=""
        )

    error = None
    try:
        appointments = get_patient_appointments(
            connection,
            patient["patient_id"]
        )
    except Error as database_error:
        logger.error(
            "Patient appointment lookup failed (MySQL error %s).",
            getattr(database_error, "errno", "unknown")
        )
        appointments = []
        error = "Unable to load your appointments right now."
    finally:
        connection.close()

    return render_template(
        "my_appointments.html",
        patient=patient,
        appointments=appointments,
        error=error
    )


@app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@role_required("PATIENT")
def cancel_appointment(appointment_id):
    patient = get_current_user()
    connection = get_db_connection()
    if not connection:
        return render_template(
            "index.html",
            error="Database connection failed. Please try again in a moment.",
            symptoms=""
        )

    try:
        status, _ = cancel_booked_appointment(
            connection,
            appointment_id,
            patient["patient_id"]
        )
        if status == "CANCELLED":
            flash("The booked appointment was cancelled.", "success")
        elif status == "COMPLETED":
            flash("Completed appointments cannot be cancelled.", "error")
        elif status == "NOT_FOUND":
            flash("The appointment could not be found.", "error")
        else:
            flash("Only booked appointments can be cancelled.", "error")
    except Error as error:
        logger.error(
            "Appointment cancellation failed (MySQL error %s).",
            getattr(error, "errno", "unknown")
        )
        flash("The appointment could not be cancelled. Please try again.", "error")
    finally:
        connection.close()

    return redirect(url_for("my_appointments"))


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        debug=os.getenv("FLASK_DEBUG", "").strip().lower() == "true"
    )