import os
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="seeker")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    jobs = db.relationship("Job", backref="recruiter", lazy=True, cascade="all, delete-orphan")
    applications = db.relationship("Application", backref="applicant", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    job_type = db.Column(db.String(40), nullable=False)
    salary = db.Column(db.String(80), default="")
    description = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recruiter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    applications = db.relationship("Application", backref="job", lazy=True, cascade="all, delete-orphan")


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    resume_link = db.Column(db.String(500), default="")
    cover_letter = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Submitted", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("applicant_id", "job_id", name="unique_user_job_application"),)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
    database_url = os.environ.get("DATABASE_URL", "sqlite:///jobconnect.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return view(*args, **kwargs)
            return wrapped
        return decorator

    def get_owned_job(job_id):
        job = db.session.get(Job, job_id)
        if job is None:
            abort(404)
        if current_user.role != "admin" and job.recruiter_id != current_user.id:
            abort(403)
        return job

    @app.context_processor
    def inject_globals():
        return {"now_year": datetime.utcnow().year}

    @app.route("/")
    def home():
        q = request.args.get("q", "").strip()
        location = request.args.get("location", "").strip()
        query = Job.query.filter_by(is_active=True)
        if q:
            term = f"%{q}%"
            query = query.filter(or_(Job.title.ilike(term), Job.company.ilike(term),
                                     Job.description.ilike(term), Job.job_type.ilike(term)))
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        jobs = query.order_by(Job.created_at.desc()).all()
        return render_template("index.html", jobs=jobs, q=q, location=location)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "seeker")
            if not name or len(name) > 100 or not email or "@" not in email:
                flash("Please enter a valid name and email.", "error")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
            elif role not in ("seeker", "recruiter"):
                flash("Please choose a valid account type.", "error")
            elif User.query.filter_by(email=email).first():
                flash("An account with this email already exists. Please log in.", "error")
            else:
                user = User(name=name, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Your account has been created successfully.", "success")
                return redirect(url_for("dashboard"))
        return render_template("auth.html", mode="register")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user, remember=bool(request.form.get("remember")))
                flash("Welcome back!", "success")
                next_url = request.args.get("next", "")
                if next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                return redirect(url_for("dashboard"))
            flash("Incorrect email or password.", "error")
        return render_template("auth.html", mode="login")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        if current_user.role == "recruiter":
            jobs = Job.query.filter_by(recruiter_id=current_user.id).order_by(Job.created_at.desc()).all()
            applications = (Application.query.join(Job)
                            .filter(Job.recruiter_id == current_user.id)
                            .order_by(Application.created_at.desc()).all())
            return render_template("recruiter_dashboard.html", jobs=jobs, applications=applications)
        applications = Application.query.filter_by(applicant_id=current_user.id).order_by(Application.created_at.desc()).all()
        return render_template("seeker_dashboard.html", applications=applications)

    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        job = db.session.get(Job, job_id)
        if job is None or (not job.is_active and (not current_user.is_authenticated or
            (current_user.role != "admin" and current_user.id != job.recruiter_id))):
            abort(404)
        already_applied = False
        if current_user.is_authenticated and current_user.role == "seeker":
            already_applied = Application.query.filter_by(applicant_id=current_user.id, job_id=job.id).first() is not None
        return render_template("job_detail.html", job=job, already_applied=already_applied)

    @app.route("/jobs/<int:job_id>/apply", methods=["POST"])
    @role_required("seeker")
    def apply(job_id):
        job = db.session.get(Job, job_id)
        if job is None or not job.is_active:
            abort(404)
        if Application.query.filter_by(applicant_id=current_user.id, job_id=job_id).first():
            flash("You have already applied for this job.", "info")
            return redirect(url_for("job_detail", job_id=job_id))
        resume_link = request.form.get("resume_link", "").strip()
        if resume_link and not (resume_link.startswith("https://") or resume_link.startswith("http://")):
            flash("Resume link must start with http:// or https://.", "error")
            return redirect(url_for("job_detail", job_id=job_id))
        application = Application(
            applicant_id=current_user.id, job_id=job_id,
            resume_link=resume_link,
            cover_letter=request.form.get("cover_letter", "").strip()
        )
        db.session.add(application)
        db.session.commit()
        flash("Application submitted successfully!", "success")
        return redirect(url_for("dashboard"))

    @app.route("/jobs/new", methods=["GET", "POST"])
    @role_required("recruiter", "admin")
    def create_job():
        if request.method == "POST":
            fields = {key: request.form.get(key, "").strip() for key in
                      ("title", "company", "location", "job_type", "salary", "description")}
            if not all(fields[k] for k in ("title", "company", "location", "job_type", "description")):
                flash("Please complete all required fields.", "error")
            else:
                job = Job(**fields, recruiter_id=current_user.id)
                db.session.add(job)
                db.session.commit()
                flash("Job published successfully.", "success")
                return redirect(url_for("dashboard"))
        return render_template("job_form.html", job=None)

    @app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    @role_required("recruiter", "admin")
    def edit_job(job_id):
        job = get_owned_job(job_id)
        if request.method == "POST":
            for field in ("title", "company", "location", "job_type", "salary", "description"):
                value = request.form.get(field, "").strip()
                if field in ("title", "company", "location", "job_type", "description") and not value:
                    flash("Please complete all required fields.", "error")
                    return render_template("job_form.html", job=job)
                setattr(job, field, value)
            db.session.commit()
            flash("Job updated.", "success")
            return redirect(url_for("dashboard"))
        return render_template("job_form.html", job=job)

    @app.route("/jobs/<int:job_id>/delete", methods=["POST"])
    @role_required("recruiter", "admin")
    def delete_job(job_id):
        job = get_owned_job(job_id)
        db.session.delete(job)
        db.session.commit()
        flash("Job and its applications were deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/applications/<int:application_id>/status", methods=["POST"])
    @role_required("recruiter", "admin")
    def update_application_status(application_id):
        application = db.session.get(Application, application_id)
        if application is None:
            abort(404)
        if current_user.role != "admin" and application.job.recruiter_id != current_user.id:
            abort(403)
        status = request.form.get("status", "")
        if status not in ("Submitted", "Under review", "Shortlisted", "Rejected"):
            abort(400)
        application.status = status
        db.session.commit()
        flash("Application status updated.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():
        users = User.query.order_by(User.created_at.desc()).all()
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        applications = Application.query.order_by(Application.created_at.desc()).all()
        return render_template("admin_dashboard.html", users=users, jobs=jobs, applications=applications)

    @app.route("/admin/users/<int:user_id>/role", methods=["POST"])
    @role_required("admin")
    def change_user_role(user_id):
        user = db.session.get(User, user_id)
        if user is None:
            abort(404)
        new_role = request.form.get("role", "")
        if new_role not in ("seeker", "recruiter", "admin"):
            abort(400)
        if user.id == current_user.id and new_role != "admin":
            flash("You cannot remove your own admin role.", "error")
        else:
            user.role = new_role
            db.session.commit()
            flash("User role updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/jobs/<int:job_id>/toggle", methods=["POST"])
    @role_required("admin")
    def toggle_job(job_id):
        job = db.session.get(Job, job_id)
        if job is None:
            abort(404)
        job.is_active = not job.is_active
        db.session.commit()
        flash("Job visibility updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="The page or job you're looking for was not found."), 404

    with app.app_context():
        db.create_all()
        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "")
        if admin_email and admin_password and not User.query.filter_by(email=admin_email).first():
            admin = User(name="Site Admin", email=admin_email, role="admin")
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
