# Symptom-Based Doctor / Clinic Finder

This DBMS mini-project helps a user describe symptoms in natural language, finds the closest stored symptom example using semantic similarity, displays the related pre-seeded specialties and doctors, and provides appointment-slot booking.

It is a demonstration and discovery tool, not a medical diagnostic system. It does not provide medical advice or emergency triage.

## Technology

- Python and Flask
- Flask/Jinja2 templates with HTML, CSS, and JavaScript
- MySQL with InnoDB tables, constraints, stored procedures, functions, triggers, and views
- Redis for short-lived symptom-match and doctor-recommendation cache entries
- Sentence Transformers (`all-MiniLM-L6-v2`) and scikit-learn cosine similarity
- Werkzeug password hashing, Flask signed sessions, Flask-WTF CSRF protection, and `python-dotenv`

There is no Next.js frontend or separate vector database. Authentication uses application roles `PATIENT` and `ADMIN`; MySQL technical roles are configured separately for Flask and catalog maintenance. There is no audit log or Flask consultation/prescription workflow.

## Local setup (Windows PowerShell)

Use Python 3.11 or newer that is compatible with the installed Sentence Transformers dependencies.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally:

- Set `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME` to your existing MySQL connection settings. Do not commit `.env` or paste credentials into source code.
- Set `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, and `REDIS_CACHE_TTL` for the local Redis instance. Defaults are `localhost`, `6379`, database `0`, and 300 seconds. Redis password support is available through `REDIS_PASSWORD` if your Redis server requires one; do not put real secrets in `.env.example`.
- Set `FLASK_SECRET_KEY` to a long random value. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` and paste the result into `.env`.
- Keep `SESSION_COOKIE_SECURE=false` for local HTTP development; set it to `true` when the app is served over HTTPS.
- `SESSION_LIFETIME_HOURS` defaults to 8. The session cookie is HTTP-only and uses `SameSite=Lax`.
- Keep `FLASK_DEBUG=false` unless you intentionally enable the local development debugger.

The project does not rotate MySQL credentials. The connection code now reads the password from `DB_PASSWORD`; copy the existing local password into `.env` yourself if it is not already configured in your environment.

## Redis caching

MySQL remains the primary relational database and the source of truth for symptoms, specializations, doctors, and appointments. Redis is an optional, temporary performance layer; if Redis is stopped or unreachable, searches continue using the existing MySQL and semantic-search workflow.

The `/search` flow has two independently cached stages:

1. A symptom query is trimmed and case-folded, hashed into a deterministic cache key, then matched by the existing Sentence Transformers/cosine-similarity algorithm when the cache misses.
2. The existing MySQL specialization/doctor join results are cached by `search_id`.

Both entries use `REDIS_CACHE_TTL` (300 seconds by default). Cached JSON retains the existing template data and does not change the search response format. Expiration bounds staleness even if a data change is not followed by invalidation. After changing doctors, specializations, or their associations in an administrative/data-maintenance workflow, call `invalidate_caches()` from `app/cache.py` after committing the MySQL change. This advances a shared Redis cache version instead of deleting unrelated Redis data; old entries age out by TTL. The current Flask app has no doctor/specialization editing routes.

Cache hit/miss counts are process-local counters and reset when Flask restarts. A cache miss means the relevant cached value was absent or Redis was unavailable; Redis outages are logged and bypassed without interrupting MySQL searches. Cache keys contain hashes, not raw symptom text.

### Start Redis on Windows

For a first-time Docker setup, create the container:

```powershell
docker run --name symptom-redis -p 6379:6379 -d redis:7
docker exec symptom-redis redis-cli ping
```

The expected response to the ping is `PONG`. For a container that already exists, start it with `docker start symptom-redis` instead of running the create command again. The app expects the host port `6379` to be available.

Install the Python dependencies if needed:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

### Cache API

- `GET /api/cache/health` pings Redis and returns `{"status":"healthy","redis":"connected"}` with HTTP 200, or an unhealthy JSON response with HTTP 503.
- `GET /api/cache/stats` returns `hits`, `misses`, `hit_ratio`, and `redis_connected`. The ratio is `hits / (hits + misses)` and is `0.0` before any cache lookups.

### Cache tests and performance demo

Run the application and tests from the project root:

```powershell
python .\app.py
python -m unittest discover -s .\app -p "test_*.py"
```

Redis feature tests use an in-memory Redis double and do not flush or modify the running Redis database. Existing MySQL integration tests still require a separately configured `TEST_DB_NAME`.

To compare the uncached MySQL + semantic search, a cold cache miss, and a repeated warm cache hit against the configured MySQL and Redis instances:

```powershell
python .\app\performance_demo.py "Chest tightness and shortness of breath while walking"
```

The script uses `time.perf_counter()`, reports actual timings, cache outcomes, and MySQL query counts, and deletes only the two exact cache entries for the supplied query to make the cold-miss measurement repeatable. It does not flush Redis. Run it with MySQL, Redis, and the local `.env` configuration available; the first semantic-model use may also incur model-load time.

## Database setup

Start MySQL and create/load the project database in this order for a fresh database:

1. `database/01_schema.sql`
2. `database/02_data.sql`
3. `database/07_views.sql`
4. `database/08_indexes.sql`
5. `database/09_procedures.sql`
6. `database/10_functions.sql`
7. `database/11_triggers.sql`

`database/03_basic_queries.sql` through `database/06_subqueries.sql` are example queries and are optional. Do not automatically execute `database/12_transactions.sql` against a database containing valuable records: it includes committed appointment test rows and cleanup deletes.

For an existing database, `database/15_authentication.sql` adds the account table and public-registration routine without changing existing patient or appointment rows. `database/16_mysql_rbac.sql` creates the technical MySQL accounts and grants; review the account/host details and get DBA approval before executing it.

`database/13_allow_cancelled_slot_rebooking.sql` is a one-time migration for an existing database that still has the old unique key `uq_appointment_slot`. Back up schema and data and review the preflight query before running it. Do not run it after creating a fresh database from the updated `01_schema.sql`, which already contains the new active-slot constraint.

The original demo appointment slots in `database/02_data.sql` are dated October 5-9, 2026. `database/14_seed_future_demo_slots.sql` is an idempotent demo-data script that repeats only those recorded doctor/time combinations on the matching weekdays for the next 30 days. It does not update or delete existing slot or appointment rows. This assumes a repeating demonstration schedule; do not treat it as verified provider availability. Execute it in MySQL Workbench with `symptom_doctor_finder` selected. After a successful insert, invalidate Redis from the project root using the PowerShell command in the SQL script comments. The app does not cache slot availability today, but the invalidation keeps cache contents consistent after data maintenance.

The application expects the database name in `DB_NAME` (the example uses `symptom_doctor_finder`).

## Authentication and roles

Patient registration, login, and logout are available from the Flask navigation. Passwords are stored as Werkzeug password hashes; plaintext passwords are never saved. Registration hashes the password in Python and calls `register_patient_account`, a MySQL `SQL SECURITY DEFINER` routine that creates the `patient` and linked `auth_user` rows in one transaction. The routine accepts no role argument and always inserts `PATIENT`; passwords must be 12-128 characters.

The `auth_user` table is added by `database/15_authentication.sql`; existing tables and appointment data are not dropped or recreated. Existing patient records are deliberately not linked to new accounts just because their email matches: email alone does not establish ownership. A person whose email is already in the patient table must ask an administrator to verify and link their account.

- **PATIENT** accounts may book appointments, view their own appointment history, view their own confirmation pages, and cancel only their own appointments in `BOOKED` status. Patient identity comes from the signed-in account and is checked against MySQL; browser-supplied patient IDs are not used as proof of identity.
- **ADMIN** accounts may open `/admin`, which displays aggregate patient, doctor, appointment, and future-slot counts. It does not expose patient records or appointment details. Public patient registration cannot create administrators.
- Search and cache-health/statistics endpoints remain public. CSRF protection remains enabled on all state-changing forms.

Create the initial admin account interactively after applying the authentication migration and RBAC script:

```powershell
.\.venv\Scripts\python.exe .\app\create_admin.py
```

The script prompts for an email and password, stores only a password hash, and refuses to create another admin when one already exists. It connects with the separate `ADMIN_DB_USER` and `ADMIN_DB_PASSWORD` settings, not the Flask `DB_USER`. The trusted database account needs only `SELECT` and `INSERT` on `symptom_doctor_finder.auth_user`; the supplied RBAC script provisions a local `sdf_admin_creator` account with those table privileges. Do not pass passwords on the command line or use this account for the Flask application.

### MySQL database-level roles

`database/16_mysql_rbac.sql` defines technical MySQL roles and local database accounts. The `sdf_app_role` receives only the table reads/writes and procedure execution used by Flask; it cannot directly insert into `patient` or `auth_user`, but receives `EXECUTE` on the fixed-role patient-registration routine. `sdf_registration_definer` is a locked, non-login account with only `SELECT` and `INSERT` on those two tables. The public routine has an explicit `DEFINER` and `SQL SECURITY DEFINER`; the other procedures in `database/09_procedures.sql` use `SQL SECURITY INVOKER`. The catalog-maintenance role can read and modify only `clinic`, `doctor`, `specialization`, and `appointment_slot`. A distinct `sdf_admin_creator_role` can read and insert only `auth_user` for the trusted offline admin utility. No application role gets global privileges, schema DDL, `GRANT OPTION`, or account-management privileges.

This is separate from application-level PATIENT/ADMIN checks: Flask uses the `sdf_app` MySQL principal for both web roles, while it enforces each user’s application permissions and patient ownership. Never run the web app as MySQL `root`.

The RBAC script creates `sdf_app`@`localhost`, `sdf_db_maintainer`@`localhost`, and `sdf_admin_creator`@`localhost` with MySQL-generated random passwords. **No SQL has been executed by this change.** Before running it, review the account names and host restrictions and use a DBA account to execute the scripts. Securely capture each generated password: configure `sdf_app` as `DB_USER`/`DB_PASSWORD` for Flask, and configure the trusted admin account as `ADMIN_DB_USER`/`ADMIN_DB_PASSWORD` for `create_admin.py`. Store the maintenance password separately and do not use it for Flask or admin creation.

For a fresh database, apply the schema/data/object scripts (including `database/09_procedures.sql`) first, then `database/15_authentication.sql`, then `database/16_mysql_rbac.sql`, using a DBA account. For an existing installation, back up first and apply `database/09_procedures.sql` to recreate its procedures with invoker security, then `database/15_authentication.sql`, then the reviewed `database/16_mysql_rbac.sql`; do not rerun schema/data creation. If the older version of `16_mysql_rbac.sql` was already applied, inspect `SHOW GRANTS` and run `database/17_mysql_rbac_privilege_cleanup.sql` to remove its three legacy privileges. Run that cleanup only when those grants are present; MySQL can reject a `REVOKE` for a privilege that is not present. The authentication migration creates/locks the registration definer and grants only the two required table privileges. The scripts need DBA-level account/routine provisioning privileges, including permission to create a routine with the explicit definer. Applying `15_authentication.sql` again replaces the registration procedure and may remove its routine-level `EXECUTE` grant, so reapply `16_mysql_rbac.sql` afterward. Do not execute the scripts against a live database until the account requirements are confirmed.

### Local patient/admin login walkthrough

1. Apply `database/09_procedures.sql` (to set existing search/history procedures to `SQL SECURITY INVOKER`), then `database/15_authentication.sql`, then reviewed `database/16_mysql_rbac.sql` to `symptom_doctor_finder` using an authorized DBA account. Existing patient and appointment rows are retained. If the older RBAC script was previously applied, inspect grants and conditionally run `database/17_mysql_rbac_privilege_cleanup.sql` as described above.
2. Capture MySQL-generated credentials securely. Configure `.env` with `DB_USER=sdf_app` and its generated `DB_PASSWORD`, plus `ADMIN_DB_USER=sdf_admin_creator` and its separate generated `ADMIN_DB_PASSWORD`. Keep the admin-creator credentials only for the trusted utility.
3. Create the first admin interactively with `.\.venv\Scripts\python.exe .\app\create_admin.py`. Use a unique admin email and a 12-128 character password.
4. Start Redis if using the existing cache, then run `python .\app.py`.
5. Open `http://127.0.0.1:5000/register` and register a new patient account. Then log out and use `/login` to verify patient login. Search for a doctor, book a future available slot, and use **My appointments** to view or cancel only that account's eligible bookings.
6. Log in using the admin credentials created in step 3. The app directs the admin to `/admin`; only aggregate counts are shown. Patient registration never creates an admin.

The existing seeded patient emails cannot be claimed through public registration. This is intentional; a verified account-linking process is needed before those old patient records can be accessed by an account.

## Run the application and tests

From the project root, with `.env` configured:

```powershell
python app.py
```

The development server binds to `127.0.0.1`. Debugging is off by default. To enable the Flask debugger for local development only, set `FLASK_DEBUG=true` in `.env`, then restart the app. Do not expose the Flask development server or debugger to a public network.

Run the semantic-search regression checks:

```powershell
python .\app\test_semantic_db.py
```

Run the application and authentication/booking tests from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\app -p "test_*.py"
```

Tests that verify concurrent MySQL unique-index behavior require an explicitly configured isolated test database. They must never use `DB_NAME` or the project database.

## Database model and relationships

The ten existing business entities are `clinic`, `doctor`, `specialization`, `patient`, `appointment_slot`, `appointment`, `symptom_search`, `symptom_specialization`, `consultation`, and `prescription`. The additive `auth_user` table links patient accounts to patient rows; admin accounts have no patient link.

- A clinic has many doctors; each doctor references one clinic.
- A specialization has many doctors; each doctor references one specialization.
- A doctor has many appointment slots.
- A patient has many appointments. A booking is represented by `appointment.patient_id` and `appointment.slot_id`; `appointment` does not store a separate `doctor_id`.
- A slot can have multiple historical appointment rows when earlier rows are cancelled, but at most one non-cancelled appointment may reserve that slot. Slot availability is derived from appointment status; there is no `appointment_slot.is_available` column.
- An appointment has zero or one consultation (`consultation.appointment_id` is unique); a consultation may have many prescriptions.
- A patient has many symptom searches. `symptom_specialization` joins searches to specializations and stores an association score.

See the editable Mermaid source at [`database/ER_diagram.mmd`](./database/ER_diagram.mmd) and the rendered [`Healthcare Appointment ER Diagram.png`](./Healthcare%20Appointment%20ER%20Diagram.png). The authentication table is defined by `database/15_authentication.sql`; its presence in a live MySQL database has not been verified.

## Database objects

The SQL scripts define these objects:

- **Stored procedures:** `get_doctors_by_specialization`, `get_doctor_slots`, `get_experienced_doctors`, `get_patient_appointments`.
- **Functions:** `get_experience_category`, `calculate_age`, `get_similarity_category`.
- **Triggers:** `before_appointment_insert` (rejects an already occupied slot), `before_appointment_timestamp` (sets a missing booking timestamp), and `before_doctor_insert` (rejects negative experience).
- **Views:** `doctor_directory`, `appointment_details`, `semantic_search_results`, `doctor_appointment_summary`.

The schema includes primary and foreign keys, unique constraints, check constraints, and indexes. There is no audit-log table or audit trigger.

## Semantic-search behavior

The application embeds the user description and the stored `symptom_search.symptom_text` examples with Sentence Transformers, then uses cosine similarity to select the closest stored example. The score beside the matched example is the query-to-example cosine similarity.

Specialty associations and their stored scores come from the pre-seeded `symptom_specialization` rows for the selected example; they are not recalculated for each live user query. The specialty score shown on results is therefore labelled as a stored symptom-specialization association score, not as the live query's cosine score.

Search history in the home-page UI is held in browser `localStorage`; live query text and query scores are not persisted to MySQL by the search route.

## Booking, cancellation, and rebooking

`get_doctor_slots` lists the selected doctor's slots for the requested date when no appointment with a status other than `CANCELLED` references a slot. Booking requires a signed-in patient and creates the appointment for that account's linked patient record in a transaction. The database continues to enforce active-slot uniqueness.

The booking page queries and displays slots for the date selected in its date form; the source does not pin availability to November 17. The source seed data contains slots only on October 5-9, 2026, while the separate future-demo script repeats those weekday/time patterns over the next 30 days. Without inspecting the live MySQL rows, the earlier observation that only November 17 appeared cannot be attributed conclusively to the UI or the data actually loaded. The availability procedure and booking trigger exclude elapsed start times; apply the updated `database/09_procedures.sql` and `database/11_triggers.sql` to an existing database under an approved migration process before expecting those database-side checks to take effect.

For existing databases, the rebooking migration replaces the all-status unique slot key with a unique index over a generated `active_slot_id`: cancelled appointments produce `NULL`, while BOOKED and COMPLETED appointments reserve the slot. This retains cancelled appointment history and lets the database prevent concurrent active double-booking. The procedure and existing insert trigger use the same cancelled-versus-active rule.

Cancellation is limited to the signed-in patient's own `BOOKED` appointments, uses a row lock and conditional update, and cannot cancel `COMPLETED` appointments. Appointment confirmation queries are also constrained by the authenticated patient ID. Admin dashboard metrics are aggregate-only.

## Known limitations and future work

- Existing seeded patients do not have accounts and cannot self-claim their rows; account linking needs a separate verified administrative process.
- Application admin users currently have a read-only aggregate dashboard; doctor/schedule management remains a separate MySQL maintenance task.
- Consultation and prescription tables exist, but the Flask application has no management routes or templates for them.
- No audit logging is implemented.
- Demo appointment slots are demonstration data, not verified schedules.
- The stored symptom examples and specialization associations are sample knowledge data, not a clinical recommendation engine.
- The project has no deployment-grade WSGI server, user-management system, or production secret-management workflow.

## Technology justification

- **Flask** keeps the existing Python search pipeline, session-based authentication, CSRF protection, templates, and database access in one small application without introducing a second frontend stack.
- **MySQL/InnoDB** is the durable source of truth for clinics, doctors, appointment slots, patients, appointments, and clinical records. Relational constraints and transactions protect identity links and prevent conflicting active bookings.
- **Redis** is an optional low-latency, short-lived cache for repeated symptom matches and doctor recommendations. It is not the permanent record store and does not provide the project's relational integrity or appointment booking constraints.
- **Sentence Transformers and cosine similarity** provide semantic comparison between a submitted symptom description and the project's stored example descriptions. This is application-level embedding and similarity computation, not a vector database: the project does not persist vectors in a vector store or provide vector-index CRUD.

## SQL demonstrations

### DML operations

Open `database/18_dml_demo.sql` in MySQL Workbench and run the complete script in one connection. It demonstrates `INSERT`, `SELECT`, `UPDATE`, and `DELETE` using only the session-scoped `dml_demo_sample` temporary table. Closing the SQL session drops that table. The script does not change application tables or records. Use a development/DBA connection with permission to create temporary tables; the least-privilege Flask account is not intended for this exercise.

### Recursive CTE

Run `database/19_recursive_cte_demo.sql` on MySQL 8.0. It uses a recursive CTE anchor to select the current database date, adds one day in each recursive member, and terminates after seven dates. A separate CTE counts future, unbooked appointment slots for those dates; `LEFT JOIN` returns dates with zero slots too. It is a read-only query and does not insert demo slots. Slot data may be synthetic and must not be interpreted as verified clinic availability.

## Redis CRUD demonstration (not application persistence)

The application uses Redis as a cache, not as the authoritative NoSQL record store. For an isolated, temporary CRUD exercise, configure `.env` and start the configured Redis service, then run:

```powershell
.\.venv\Scripts\python.exe .\app\redis_crud_demo.py
```

The demonstration creates a random UUID key only under `doctor_finder:demo:crud:`, reads it, updates it, and deletes that exact key. It uses sample, non-sensitive data and a short TTL. It never scans or flushes Redis and leaves unrelated application cache keys alone. Unit tests use an in-memory Redis double and do not require or modify a running Redis instance:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\app -p "test_redis_crud_demo.py" -v
```

This illustrates basic Redis key-value CRUD and expiry, not a general document database, relational store, or vector database.

## HTTP route summary

| Method and path | Purpose | Access |
|---|---|---|
| `GET /` | Home page and symptom form | Public |
| `POST /search` | Run symptom matching and render doctor recommendations; requires the form's CSRF token | Public |
| `GET, POST /register` | Register a PATIENT account | Public; CSRF on POST |
| `GET, POST /login` | Authenticate a user | Public; CSRF on POST |
| `POST /logout` | Clear the current session | Signed-in session; CSRF required |
| `GET, POST /book/<doctor_id>` | View available future slots and book one | PATIENT; CSRF required on POST |
| `GET /appointment-confirmation/<appointment_id>` | View the signed-in patient's own booking | PATIENT; ownership checked |
| `GET /my-appointments` | List the signed-in patient's appointments | PATIENT |
| `POST /appointments/<appointment_id>/cancel` | Cancel an eligible owned appointment | PATIENT; CSRF and ownership checks |
| `GET /admin` | View aggregate dashboard counts | ADMIN |
| `GET /api/cache/health` | Redis-only connectivity status | Public; HTTP 200 or 503 |
| `GET /api/cache/stats` | Process-local cache hits, misses, ratio, and Redis status | Public |
| `GET /health` | Separate MySQL and Redis status fields | Public; HTTP 200 when both are reachable, otherwise 503 |

The health endpoint intentionally does not include credentials, connection strings, or raw database errors. A `503` from `/health` reports a degraded dependency state; the `mysql` and `redis` fields identify which dependency failed.
