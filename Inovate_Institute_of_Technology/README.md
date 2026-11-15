# Inovate Institute of Technology

A self-contained Python 3.11+ WSGI website with a browser-based course catalogue, program roadmaps, admissions form and private content dashboard. The migrated public content is in content.json. Python and browser standard libraries handle the application. No npm build or pip packages are required.

## Run locally
From this directory:
```sh
export INSTITUTE_ADMIN_PASSWORD='your-own-long-unique-password'
python3 app.py
```
Open http://127.0.0.1:8000/ for the public website and http://127.0.0.1:8000/#/admin for staff. Choose your own password of at least 12 characters. The displayed example is for local setup and should be replaced. PORT overrides the default 8000.

## cPanel / Passenger
Extract the project to an application directory outside public_html. In Setup Python App select Python 3.11 or later, set the application root to that directory, and assign the root URL of a dedicated HTTPS domain or subdomain. Use passenger_wsgi.py as startup file and application as entry point. Set INSTITUTE_ADMIN_PASSWORD, INSTITUTE_HTTPS=1 and INSTITUTE_DB to an absolute writable SQLite file path outside the document root. Restart the app. Do not enable directory browsing or serve the application directory as static files.

SQLite initializes on first use. By default it lives in ~/.inovate-institute/site.sqlite3. Keep that file across updates. Use SQLite's backup command or stop the app before copying it for backup. The database contains personal enquiry information. Restrict access to the hosting account. The seed JSON is used only for a new database.

## Staff workflow
Use Staff sign in in the footer. Website content opens a section editor. Expand records to edit fields or add and remove entries, then publish. Course and program IDs are unique lowercase slugs. Keep existing IDs to preserve shared links. Conflicting edits require a reload. The admissions inbox supports searching, filtering and moving enquiries between New, Contacted and Closed. Submission records are available here immediately; follow-up is manual.

## Verification
Run `python3 -m unittest discover -s tests -v` from the project directory. The suite uses a temporary database and covers public content and assets, invalid form submissions, duplicate request handling, sign-in and sign-out, enquiry status changes, publication, editing conflicts and invalid content.
