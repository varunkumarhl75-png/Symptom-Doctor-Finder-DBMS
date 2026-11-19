import os
import re
import threading
import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import mysql.connector

os.environ.setdefault("FLASK_SECRET_KEY", "unit-test-only-secret")

import app as app_module
import db as db_module
from mysql.connector.errors import IntegrityError


class FakeStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.patients = {}
        self.appointments = []
        self.next_patient_id = 1
        self.next_appointment_id = 1
        self.fail_appointment_insert = False


class FakeConnection:
    def __init__(self, store):
        self.store = store
        self.pending_patients = []
        self.pending_appointments = []
        self.pending_updates = []
        self.lock_held = False

    def cursor(self, dictionary=False):
        return FakeCursor(self, dictionary)

    def start_transaction(self):
        pass

    def commit(self):
        for patient in self.pending_patients:
            self.store.patients[patient["email"]] = patient
        self.store.appointments.extend(self.pending_appointments)
        for appointment in self.pending_updates:
            appointment["status"] = "CANCELLED"
        self._finish_transaction()

    def rollback(self):
        self._finish_transaction()

    def close(self):
        self.rollback()

    def _finish_transaction(self):
        self.pending_patients.clear()
        self.pending_appointments.clear()
        self.pending_updates.clear()
        if self.lock_held:
            self.lock_held = False
            self.store.lock.release()


class FakeCursor:
    def __init__(self, connection, dictionary):
        self.connection = connection
        self.dictionary = dictionary
        self.rows = []
        self.rowcount = 0
        self.lastrowid = None

    def execute(self, query, parameters=None):
        normalized = " ".join(query.lower().split())
        parameters = parameters or ()

        if normalized.startswith("select patient_id, name, phone from patient"):
            patient = self.connection.store.patients.get(parameters[0])
            self.rows = [patient] if patient else []
            return

        if normalized.startswith("insert into patient"):
            patient_id = self.connection.store.next_patient_id
            self.connection.store.next_patient_id += 1
            patient = {
                "patient_id": patient_id,
                "name": parameters[0],
                "email": parameters[1],
                "phone": parameters[2]
            }
            self.connection.pending_patients.append(patient)
            self.lastrowid = patient_id
            self.rowcount = 1
            return

        if normalized.startswith("insert into appointment"):
            if self.connection.store.fail_appointment_insert:
                raise IntegrityError(
                    msg="Duplicate entry for key 'uq_appointment_active_slot'"
                )
            if not self.connection.lock_held:
                self.connection.store.lock.acquire()
                self.connection.lock_held = True
            patient_id, slot_id, notes = parameters
            existing = (
                self.connection.store.appointments
                + self.connection.pending_appointments
            )
            if any(
                item["slot_id"] == int(slot_id)
                and item["status"] != "CANCELLED"
                for item in existing
            ):
                raise IntegrityError(
                    msg="Duplicate entry for key 'uq_appointment_active_slot'"
                )
            appointment_id = self.connection.store.next_appointment_id
            self.connection.store.next_appointment_id += 1
            self.connection.pending_appointments.append({
                "appointment_id": appointment_id,
                "patient_id": patient_id,
                "slot_id": int(slot_id),
                "status": "BOOKED",
                "notes": notes
            })
            self.lastrowid = appointment_id
            self.rowcount = 1
            return

        if normalized.startswith(
            "select patient_id, status from appointment where appointment_id = %s and patient_id = %s for update"
        ):
            if not self.connection.lock_held:
                self.connection.store.lock.acquire()
                self.connection.lock_held = True
            appointment = next(
                (
                    item for item in self.connection.store.appointments
                    if item["appointment_id"] == parameters[0]
                    and item["patient_id"] == parameters[1]
                ),
                None
            )
            self.rows = [{
                "patient_id": appointment["patient_id"],
                "status": appointment["status"]
            }] if appointment else []
            return

        if (
            normalized.startswith("select a.appointment_id, a.patient_id, a.status")
            and "where a.appointment_id = %s" in normalized
        ):
            self.rows = [{
                "appointment_id": parameters[0],
                "patient_id": 7,
                "status": "BOOKED",
                "notes": "",
                "patient_name": "Demo Patient",
                "doctor_name": "Dr Demo",
                "specialization": "General Medicine",
                "clinic_name": "Demo Clinic",
                "appointment_date": "2026-11-02",
                "start_time": "09:00:00",
                "end_time": "09:30:00"
            }] if parameters[1] == 7 else []
            return

        if normalized.startswith("update appointment"):
            appointment = next(
                (
                    item for item in self.connection.store.appointments
                    if item["appointment_id"] == parameters[0]
                    and item["patient_id"] == parameters[1]
                    and item["status"] == "BOOKED"
                ),
                None
            )
            self.rowcount = 1 if appointment else 0
            if appointment:
                self.connection.pending_updates.append(appointment)
            return

        raise AssertionError("Unexpected SQL in test double: " + normalized)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        pass


class AppSafetyTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.appointment_date = (date.today() + timedelta(days=1)).isoformat()
        self.app = app_module.app
        self.get_available_slots = app_module.get_available_slots
        self.app.config.update(
            TESTING=True,
            WTF_CSRF_ENABLED=True
        )
        self.patches = [
            patch.object(app_module, "get_current_user", return_value={
                "user_id": 1,
                "email": "demo@example.test",
                "role": "PATIENT",
                "patient_id": 7,
                "patient_name": "Demo Patient",
                "patient_phone": "9876543210"
            }),
            patch.object(
                app_module,
                "get_db_connection",
                side_effect=lambda: FakeConnection(self.store)
            ),
            patch.object(app_module, "get_doctor_details", return_value={
                "doctor_id": 1,
                "doctor_name": "Dr Demo",
                "specialization": "General Medicine",
                "clinic_name": "Demo Clinic",
                "qualification": "MD",
                "experience_years": 5,
                "phone": "9000000000"
            }),
            patch.object(app_module, "get_available_slots", side_effect=self.available_slots),
            patch.object(
                app_module,
                "get_patient_appointments",
                return_value=[]
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def available_slots(self, connection, doctor_id, appointment_date):
        return [{
            "slot_id": 41,
            "start_time": "09:00:00",
            "end_time": "09:30:00"
        }] if not any(
            item["slot_id"] == 41 and item["status"] != "CANCELLED"
            for item in self.store.appointments
        ) else []

    def token_for(self, client, path="/book/1"):
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def test_booking_page_renders_doctor_slots_and_csrf_form(self):
        client = self.app.test_client()
        response = client.get(
            "/book/1",
            query_string={"appointment_date": self.appointment_date}
        )
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Book an Appointment", page)
        self.assertIn("Dr Demo", page)
        self.assertIn("09:00:00 - 09:30:00", page)
        self.assertIn('name="csrf_token"', page)
        self.assertIn(
            'action="/book/1"',
            page
        )

    def test_booking_page_rejects_past_slot_date_without_querying_availability(self):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        with patch.object(
            app_module,
            "get_available_slots",
            wraps=app_module.get_available_slots
        ) as available_slots:
            response = self.app.test_client().get(
                "/book/1",
                query_string={"appointment_date": past_date}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Appointment dates cannot be in the past.", response.data)
        available_slots.assert_not_called()

    def test_booking_page_filters_elapsed_slots_for_today(self):
        fixed_now = datetime.combine(date.today(), time(10, 0))
        original_check = app_module.is_slot_in_future
        with patch.object(
            app_module,
            "is_slot_in_future",
            side_effect=lambda slot_date, start: original_check(
                slot_date,
                start,
                now=fixed_now
            )
        ):
            response = self.app.test_client().get(
                "/book/1",
                query_string={"appointment_date": date.today().isoformat()}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No available slots for this date.", response.data)
        self.assertNotIn(b"09:00:00 - 09:30:00", response.data)

    def test_booking_refuses_a_slot_that_passed_today(self):
        fixed_now = datetime.combine(date.today(), time(10, 0))
        original_check = app_module.is_slot_in_future
        with patch.object(
            app_module,
            "is_slot_in_future",
            side_effect=lambda slot_date, start: original_check(
                slot_date,
                start,
                now=fixed_now
            )
        ):
            client = self.app.test_client()
            token = self.token_for(client)
            response = client.post(
                "/book/1",
                data={
                    "csrf_token": token,
                    "appointment_date": date.today().isoformat(),
                    "slot_id": "41"
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"no longer available", response.data)
        self.assertEqual(self.store.appointments, [])

    def test_booking_reports_slot_that_passes_after_availability_check(self):
        client = self.app.test_client()
        token = self.token_for(client)

        class ExpiredSlotCursor:
            def execute(self, *_args):
                raise mysql.connector.Error(
                    msg="This appointment slot has already passed",
                    errno=1644
                )

            def close(self):
                pass

        class ExpiredSlotConnection(FakeConnection):
            def cursor(self, dictionary=False):
                if dictionary:
                    return super().cursor(dictionary=True)
                return ExpiredSlotCursor()

        connection = ExpiredSlotConnection(self.store)
        with patch.object(
            app_module,
            "get_db_connection",
            return_value=connection
        ):
            response = client.post(
                "/book/1",
                data={
                    "csrf_token": token,
                    "appointment_date": self.appointment_date,
                    "slot_id": "41"
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This appointment slot is no longer available.", response.data)
        self.assertEqual(self.store.appointments, [])

    def test_slot_lookup_failure_is_not_reported_as_no_availability(self):
        client = self.app.test_client()
        token = self.token_for(client)
        with patch.object(
            app_module,
            "get_available_slots",
            side_effect=mysql.connector.Error(msg="database unavailable", errno=2003)
        ):
            response = client.post(
                "/book/1",
                data={
                    "csrf_token": token,
                    "appointment_date": self.appointment_date,
                    "slot_id": "41"
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Unable to load available slots right now.", response.data)
        self.assertNotIn(b"No available slots for this date.", response.data)
        self.assertNotIn(b"no longer available", response.data)

    def test_slot_lookup_helper_propagates_database_failure(self):
        class FailedCursor:
            def callproc(self, *_args):
                raise mysql.connector.Error(msg="query failure", errno=2003)

            def close(self):
                pass

        class FailedConnection:
            def cursor(self, **_kwargs):
                return FailedCursor()

        with self.assertRaises(mysql.connector.Error):
            self.get_available_slots(
                FailedConnection(),
                1,
                self.appointment_date
            )

    def test_booking_page_does_not_show_a_booked_slot(self):
        self.store.appointments.append({
            "appointment_id": 9,
            "patient_id": 7,
            "slot_id": 41,
            "status": "BOOKED",
            "notes": ""
        })
        response = self.app.test_client().get(
            "/book/1",
            query_string={"appointment_date": self.appointment_date}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No available slots for this date.", response.data)
        self.assertNotIn(b"09:00:00 - 09:30:00", response.data)

    def book(self, client, token, slot_id="41"):
        return client.post(
            "/book/1",
            data={
                "csrf_token": token,
                "appointment_date": self.appointment_date,
                "slot_id": slot_id
            }
        )

    def test_booking_available_slot_commits_patient_and_appointment(self):
        client = self.app.test_client()
        response = self.book(client, self.token_for(client))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.store.patients), 0)
        self.assertEqual(len(self.store.appointments), 1)
        self.assertEqual(self.store.appointments[0]["status"], "BOOKED")

    def test_unavailable_slot_is_rejected_without_writes(self):
        self.store.appointments.append({
            "appointment_id": 4,
            "patient_id": 9,
            "slot_id": 41,
            "status": "BOOKED",
            "notes": ""
        })
        client = self.app.test_client()
        response = self.book(client, self.token_for(client))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"no longer available", response.data)
        self.assertEqual(self.store.patients, {})
        self.assertEqual(len(self.store.appointments), 1)

    def test_cancelled_slot_can_be_rebooked_without_losing_history(self):
        historical = {
            "appointment_id": 6,
            "patient_id": 9,
            "slot_id": 41,
            "status": "CANCELLED",
            "notes": "historical appointment"
        }
        self.store.appointments.append(historical.copy())
        client = self.app.test_client()
        response = self.book(client, self.token_for(client))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(self.store.appointments), 2)
        self.assertEqual(self.store.appointments[0]["status"], "CANCELLED")
        self.assertEqual(
            self.store.appointments[0]["notes"],
            "historical appointment"
        )
        self.assertEqual(self.store.appointments[1]["status"], "BOOKED")

    def test_failed_appointment_insert_rolls_back_new_patient(self):
        self.store.fail_appointment_insert = True
        client = self.app.test_client()
        response = self.book(client, self.token_for(client))

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"no longer available", response.data)
        self.assertEqual(self.store.patients, {})
        self.assertEqual(self.store.appointments, [])

    def test_concurrent_bookings_allow_only_one_active_appointment(self):
        availability_barrier = threading.Barrier(2)

        def simultaneous_availability(connection, doctor_id, appointment_date):
            slots = self.available_slots(connection, doctor_id, appointment_date)
            availability_barrier.wait(timeout=5)
            return slots

        with patch.object(
            app_module,
            "get_available_slots",
            side_effect=simultaneous_availability
        ):
            tokens = []
            for _ in range(2):
                client = self.app.test_client()
                tokens.append((client, self.token_for(client)))
            responses = [None, None]

            def submit(index):
                client, token = tokens[index]
                responses[index] = self.book(
                    client,
                    token,
                    slot_id="41"
                )

            threads = [
                threading.Thread(target=submit, args=(index,))
                for index in range(2)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(
            sum(response.status_code == 302 for response in responses),
            1
        )
        self.assertEqual(len(self.store.appointments), 1)
        self.assertEqual(len(self.store.patients), 0)

    def test_booked_appointment_can_be_cancelled(self):
        self.store.appointments.append({
            "appointment_id": 12,
            "patient_id": 7,
            "slot_id": 41,
            "status": "BOOKED",
            "notes": ""
        })

        status, patient_id = app_module.cancel_booked_appointment(
            FakeConnection(self.store),
            12,
            7
        )

        self.assertEqual(status, "CANCELLED")
        self.assertEqual(patient_id, 7)
        self.assertEqual(self.store.appointments[0]["status"], "CANCELLED")

    def test_completed_appointment_cannot_be_cancelled(self):
        self.store.appointments.append({
            "appointment_id": 13,
            "patient_id": 8,
            "slot_id": 42,
            "status": "COMPLETED",
            "notes": ""
        })

        status, _ = app_module.cancel_booked_appointment(
            FakeConnection(self.store),
            13,
            8
        )

        self.assertEqual(status, "COMPLETED")
        self.assertEqual(self.store.appointments[0]["status"], "COMPLETED")

    def test_csrf_is_required_for_state_changing_forms(self):
        client = self.app.test_client()
        self.assertEqual(
            client.post("/search", data={"symptoms": "headache"}).status_code,
            400
        )
        self.assertEqual(
            client.post(
                "/book/1",
                data={
                    "appointment_date": "2026-11-02",
                    "patient_name": "Demo Patient",
                    "patient_email": "demo@example.test",
                    "patient_phone": "9876543210",
                    "slot_id": "41"
                }
            ).status_code,
            400
        )

    def test_patient_cannot_cancel_another_patients_appointment(self):
        self.store.appointments.append({
            "appointment_id": 1,
            "patient_id": 8,
            "slot_id": 42,
            "status": "BOOKED",
            "notes": ""
        })
        client = self.app.test_client()
        token = self.token_for(client, "/")
        response = client.post(
            "/appointments/1/cancel",
            data={"csrf_token": token}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.store.appointments[0]["status"], "BOOKED")

    def test_patient_can_cancel_own_booked_appointment_through_route(self):
        self.store.appointments.append({
            "appointment_id": 2,
            "patient_id": 7,
            "slot_id": 42,
            "status": "BOOKED",
            "notes": ""
        })
        client = self.app.test_client()
        token = self.token_for(client, "/")
        response = client.post(
            "/appointments/2/cancel",
            data={"csrf_token": token}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.store.appointments[0]["status"], "CANCELLED")

    def test_patient_cannot_view_another_patients_confirmation(self):
        with patch.object(app_module, "get_current_user", return_value={
            "user_id": 2,
            "email": "other@example.test",
            "role": "PATIENT",
            "patient_id": 8,
            "patient_name": "Other Patient",
            "patient_phone": "9876543210"
        }):
            response = self.app.test_client().get("/appointment-confirmation/1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Appointment details could not be found.", response.data)
        self.assertNotIn(b"Demo Patient", response.data)

    def test_my_appointments_and_confirmation_pages_render_safely(self):
        client = self.app.test_client()
        appointments = client.get("/my-appointments")
        confirmation = client.get("/appointment-confirmation/1")

        self.assertEqual(appointments.status_code, 200)
        self.assertNotIn(b"Cancel Appointment", appointments.data)
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn(b"Appointment Booked Successfully", confirmation.data)


class DatabaseConfigurationTests(unittest.TestCase):
    def test_connection_uses_environment_values_without_logging_password(self):
        values = {
            "DB_HOST": "db.example.test",
            "DB_PORT": "3307",
            "DB_USER": "unit_test_user",
            "DB_PASSWORD": "unit-test-only-password",
            "DB_NAME": "unit_test_database"
        }
        with patch.dict(os.environ, values, clear=False):
            with patch.object(db_module.mysql.connector, "connect") as connect:
                connection = object()
                connect.return_value = connection
                self.assertIs(db_module.get_db_connection(), connection)

        connect.assert_called_once_with(
            host="db.example.test",
            port=3307,
            user="unit_test_user",
            password="unit-test-only-password",
            database="unit_test_database"
        )

    def test_missing_database_settings_do_not_attempt_connection(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(db_module.mysql.connector, "connect") as connect:
                self.assertIsNone(db_module.get_db_connection())
        connect.assert_not_called()

    def test_connection_error_log_does_not_include_password(self):
        password = "unit-test-secret-never-log"
        values = {
            "DB_HOST": "localhost",
            "DB_PORT": "3306",
            "DB_USER": "unit_test_user",
            "DB_PASSWORD": password,
            "DB_NAME": "unit_test_database"
        }
        with patch.dict(os.environ, values, clear=False):
            with patch.object(
                db_module.mysql.connector,
                "connect",
                side_effect=mysql.connector.Error(msg=password, errno=1045)
            ):
                with self.assertLogs("db", level="ERROR") as captured:
                    self.assertIsNone(db_module.get_db_connection())

        self.assertNotIn(password, "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
