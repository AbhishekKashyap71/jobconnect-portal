# JobConnect – Full-Stack Job Portal

A full-stack learning project using Flask, SQLAlchemy, Flask-Login, SQLite locally, and PostgreSQL-ready configuration for hosting.

## Features
- Candidate and recruiter registration
- Secure password hashing and login/logout
- Role-based access: seeker, recruiter, admin
- Job search by keyword and location
- Recruiters can create, edit and delete their own jobs
- Candidates can apply once per job
- Candidates can track their applications
- Recruiters can review applications for their own jobs and update status
- Admin dashboard: users, jobs, applications, role management and job visibility
- CSRF protection on forms
- Responsive layout

## Run locally (Windows)
1. Install Python 3.10+.
2. Extract this ZIP and open the `JobConnect_FullStack` folder in VS Code.
3. Open Terminal → New Terminal.
4. Run:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

5. Open http://127.0.0.1:5000

The local SQLite database is created automatically as `jobconnect.db`.

## Test accounts
Register two normal accounts through the website:
- one account with role **Job Seeker**
- one account with role **Recruiter**

To create the first admin account locally, set environment variables before starting the app (PowerShell):

```powershell
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="Use-A-Unique-Password-123!"
python app.py
```

Then sign in at `/login` with those credentials. Admin registration is intentionally not public.

## GitHub upload
Create a new public repository named `JobConnect`, then from this folder run:

```bash
git init
git add .
git commit -m "Build JobConnect full stack job portal"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/JobConnect.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. Do not upload `.env`, passwords, or the local database.

## Deploy on Render
1. Push the project to GitHub.
2. In Render, choose **New → Web Service** and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value.
6. Create a managed PostgreSQL database in Render (or another PostgreSQL provider), then set the web service environment variable `DATABASE_URL` to its **internal connection URL**.
7. Optionally set `ADMIN_EMAIL` and `ADMIN_PASSWORD` to create the first admin account. Use a unique strong password and do not share it.
8. Deploy.

The app supports PostgreSQL via `DATABASE_URL`; if that variable is absent, it uses local SQLite. For hosted deployment, use PostgreSQL so data survives redeploys and instance replacement. Hosting/database pricing and free-tier availability can change; check the provider's current plan before creating resources.

## Important security / production notes
This is a student project starter, not a fully audited commercial recruitment platform. It includes password hashing, CSRF protection and role checks, but before real public use add email verification, password reset, rate limiting, moderation, privacy policy/consent, backups, logging, and security review. Resume links are stored as URLs; this starter does not upload or scan resume files. Never use real sensitive personal data on an unreviewed demo.
