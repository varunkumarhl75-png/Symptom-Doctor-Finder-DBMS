import re
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

import app as app_module


class AuthStore:
    def __init__(self):
        self.patients_by_email = {}
        self.users_by_email = {}
        self.users_by_id = {}
        self.next_patient_id = 1
        self.next_user_id = 1
        self.pending_patients = []
        self.pending_users = []
        self.fail_auth_insert = False
        self.registration_calls = []


class AuthConnection:
    def __init__(self, store):
        self.store = store

    def cursor(self, dictionary=False):
        return AuthCursor(self, dictionary)

    def start_transaction(self):
        pass

    def commit(self):
        for patient in self.store.pending_patients:
            self.store.patients_by_email[patient["email"]] = patient
        for user in self.store.pending_users:
            self.store.users_by_email[user["email"]] = user
            self.store.users_by_id[user["user_id"]] = user
        self.store.pending_patients.clear()
        self.store.pending_users.clear()

    def rollback(self):
        self.store.pending_patients.clear()
        self.store.pending_users.clear()

    def close(self):
        pass


class AuthCursor:
    def __init__(self, connection, dictionary):
        self.connection = connection
        self.rows = []
        self.lastrowid = None

    def callproc(self, procedure, arguments):
        if procedure != "register_patient_account":
            raise AssertionError("Unexpected procedure: " + procedure)
        self.connection.store.registration_calls.append((procedure, tuple(arguments)))
        if len(arguments) != 6:
            raise AssertionError("Unexpected registration procedure arguments")

        name, email, phone, password_hash = arguments[:4]
        store = self.connection.store
        if email in store.patients_by_email or email in store.users_by_email:
            raise app_module.Error(
                msg="Registration email already exists",
                errno=1644
            )

        patient = {
            "patient_id": store.next_patient_id,
            "name": name,
            "email": email,
            "phone": phone
        }
        store.next_patient_id += 1
        store.pending_patients.append(patient)

        if store.fail_auth_insert:
            self.connection.rollback()
            raise app_module.Error(msg="Simulated auth_user insert failure", errno=1644)

        user = {
            "user_id": store.next_user_id,
            "email": email,
            "password_hash": password_hash,
            "role": "PATIENT",
            "patient_id": patient["patient_id"]
        }
        store.next_user_id += 1
        store.pending_users.append(user)
        self.connection.commit()
        return (*arguments[:4], patient["patient_id"], user["user_id"])

    def execute(self, query, parameters=None):
        normalized = " ".join(query.lower().split())
        parameters = parameters or ()
        store = self.connection.store

        if normalized.startswith(
            "select user_id, email, password_hash, role, patient_id from auth_user where email = %s"
        ):
            user = store.users_by_email.get(parameters[0])
            self.rows = [user] if user else []
            return

        if normalized.startswith("select u.user_id, u.email, u.role, u.patient_id,"):
            user = store.users_by_id.get(parameters[0])
            if user:
                patient = next(
                    (
                        item for item in store.patients_by_email.values()
                        if item["patient_id"] == user["patient_id"]
                    ),
                    None
                )
                self.rows = [{
                    **user,
                    "patient_name": patient["name"] if patient else None,
                    "patient_phone": patient["phone"] if patient else None
                }]
            else:
                self.rows = []
            return

        raise AssertionError("Unexpected SQL in authentication test: " + normalized)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        pass


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.store = AuthStore()
        self.app = app_module.app
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        patcher = patch.object(
            app_module,
            "get_db_connection",
            side_effect=lambda: AuthConnection(self.store)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def token_for(self, client, path):
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            response.get_data(as_text=True)
        )
        self.assertIsNotNone(token)
        return token.group(1)

    def register(self, client, token, email="patient@example.test"):
        return client.post(
            "/register",
            data={
                "csrf_token": token,
                "name": "Example Patient",
                "email": email,
                "phone": "9876543210",
                "password": "a-secure-password",
                "confirm_password": "a-secure-password"
            }
        )

    def test_successful_registration_stores_only_a_password_hash(self):
        client = self.app.test_client()
        response = self.register(client, self.token_for(client, "/register"))

        self.assertEqual(response.status_code, 302)
        user = self.store.users_by_email["patient@example.test"]
        self.assertEqual(user["role"], "PATIENT")
        self.assertEqual(user["patient_id"], 1)
        self.assertNotEqual(user["password_hash"], "a-secure-password")
        self.assertTrue(check_password_hash(user["password_hash"], "a-secure-password"))
        proc_name, args = self.store.registration_calls[0]
        self.assertEqual(proc_name, "register_patient_account")
        self.assertEqual(len(args), 6)
        self.assertEqual(args[1], "patient@example.test")
        self.assertTrue(check_password_hash(args[3], "a-secure-password"))
        with client.session_transaction() as browser_session:
            self.assertEqual(browser_session["user_id"], user["user_id"])

    def test_duplicate_registration_is_rejected(self):
        client = self.app.test_client()
        self.register(client, self.token_for(client, "/register"))
        response = self.register(
            client,
            self.token_for(client, "/register")
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.store.users_by_email), 1)

    def test_registration_cannot_claim_an_existing_patient_record(self):
        self.store.patients_by_email["patient@example.test"] = {
            "patient_id": 25,
            "name": "Existing Patient",
            "email": "patient@example.test",
            "phone": "9000000000"
        }
        client = self.app.test_client()
        response = self.register(client, self.token_for(client, "/register"))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.users_by_email, {})

    def test_registration_failure_does_not_leave_either_record(self):
        self.store.fail_auth_insert = True
        client = self.app.test_client()
        response = self.register(client, self.token_for(client, "/register"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.store.patients_by_email, {})
        self.assertEqual(self.store.users_by_email, {})

    def test_registration_cannot_assign_admin_role(self):
        client = self.app.test_client()
        token = self.token_for(client, "/register")
        response = client.post(
            "/register",
            data={
                "csrf_token": token,
                "name": "Example Patient",
                "email": "patient@example.test",
                "phone": "9876543210",
                "password": "a-secure-password",
                "confirm_password": "a-secure-password",
                "role": "ADMIN"
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.store.users_by_email["patient@example.test"]["role"],
            "PATIENT"
        )

    def test_successful_login(self):
        self.store.users_by_email["patient@example.test"] = {
            "user_id": 1,
            "email": "patient@example.test",
            "password_hash": generate_password_hash("a-secure-password"),
            "role": "PATIENT",
            "patient_id": 17
        }
        client = self.app.test_client()
        response = client.post(
            "/login",
            data={
                "csrf_token": self.token_for(client, "/login"),
                "email": "PATIENT@example.test",
                "password": "a-secure-password"
            }
        )

        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as browser_session:
            self.assertEqual(browser_session["user_id"], 1)
            self.assertEqual(browser_session["role"], "PATIENT")

    def test_incorrect_password_does_not_create_session(self):
        self.store.users_by_email["patient@example.test"] = {
            "user_id": 1,
            "email": "patient@example.test",
            "password_hash": generate_password_hash("a-secure-password"),
            "role": "PATIENT",
            "patient_id": 17
        }
        client = self.app.test_client()
        response = client.post(
            "/login",
            data={
                "csrf_token": self.token_for(client, "/login"),
                "email": "patient@example.test",
                "password": "incorrect-password"
            }
        )

        self.assertEqual(response.status_code, 401)
        with client.session_transaction() as browser_session:
            self.assertNotIn("user_id", browser_session)

    def test_logout_clears_the_session(self):
        client = self.app.test_client()
        self.register(client, self.token_for(client, "/register"))
        response = client.post(
            "/logout",
            data={"csrf_token": self.token_for(client, "/")}
        )

        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as browser_session:
            self.assertNotIn("user_id", browser_session)

    def test_patient_appointment_lookup_ignores_browser_patient_id(self):
        client = self.app.test_client()
        self.register(client, self.token_for(client, "/register"))
        with patch.object(
            app_module,
            "get_patient_appointments",
            return_value=[]
        ) as lookup:
            response = client.get("/my-appointments?patient_id=999")

        self.assertEqual(response.status_code, 200)
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args.args[1], 1)
        self.assertNotIn(b"999", response.data)

    def test_patient_cannot_access_admin_route(self):
        client = self.app.test_client()
        self.register(client, self.token_for(client, "/register"))

        self.assertEqual(client.get("/admin").status_code, 403)

    def test_admin_cannot_access_patient_appointments(self):
        admin = {
            "user_id": 90,
            "email": "admin@example.test",
            "password_hash": generate_password_hash("admin-password"),
            "role": "ADMIN",
            "patient_id": None
        }
        self.store.users_by_id[90] = admin
        client = self.app.test_client()
        with client.session_transaction() as browser_session:
            browser_session.update(
                user_id=90,
                role="ADMIN",
                email="admin@example.test"
            )

        self.assertEqual(client.get("/my-appointments").status_code, 403)

    def test_admin_can_access_admin_dashboard(self):
        admin = {
            "user_id": 90,
            "email": "admin@example.test",
            "password_hash": generate_password_hash("admin-password"),
            "role": "ADMIN",
            "patient_id": None
        }
        self.store.users_by_id[90] = admin
        client = self.app.test_client()
        with client.session_transaction() as browser_session:
            browser_session.update(
                user_id=90,
                role="ADMIN",
                email="admin@example.test"
            )
        with patch.object(
            app_module,
            "get_admin_dashboard_stats",
            return_value={
                "patient_count": 1,
                "doctor_count": 2,
                "appointment_count": 3,
                "available_slot_count": 4
            }
        ):
            response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin dashboard", response.data)
        self.assertIn(b"Available future slots", response.data)

    def test_unauthenticated_patient_routes_redirect_to_login(self):
        client = self.app.test_client()
        for path in ("/my-appointments", "/book/1", "/appointment-confirmation/1"):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].startswith("/login?"))

    def test_unauthenticated_admin_route_redirects_to_login(self):
        response = self.app.test_client().get("/admin")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/login?"))

    def test_unauthenticated_cancellation_redirects_after_csrf_validation(self):
        client = self.app.test_client()
        token = self.token_for(client, "/")
        response = client.post(
            "/appointments/1/cancel",
            data={"csrf_token": token}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/login?"))

    def test_auth_forms_require_csrf_and_session_cookies_are_configured(self):
        client = self.app.test_client()
        self.assertEqual(
            client.post("/register", data={"email": "no-token@example.test"}).status_code,
            400
        )
        self.assertEqual(
            client.post("/logout").status_code,
            400
        )
        self.assertTrue(self.app.config["WTF_CSRF_ENABLED"])
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_login_rejects_external_redirect_target(self):
        user = {
            "user_id": 4,
            "email": "patient@example.test",
            "password_hash": generate_password_hash("a-secure-password"),
            "role": "PATIENT",
            "patient_id": 17
        }
        self.store.users_by_email[user["email"]] = user
        client = self.app.test_client()
        token = self.token_for(client, "/login")
        response = client.post(
            "/login",
            data={
                "csrf_token": token,
                "email": user["email"],
                "password": "a-secure-password",
                "next": "https://evil.example/"
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")


if __name__ == "__main__":
    unittest.main()
