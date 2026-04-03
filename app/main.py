
from flask import Flask, render_template, redirect, request, session, url_for, abort
from flask_login import LoginManager, login_user, logout_user, login_required,current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_migrate import Migrate
from app.metrics import insights_analyzer
from app.models import db, Users, Projects, WorkSession
from app.utils import  is_valid_username ,is_strong_password
from dotenv import load_dotenv
import os

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "instance"))
os.makedirs(INSTANCE_PATH, exist_ok=True)


app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
    instance_path=INSTANCE_PATH,
    instance_relative_config=True )
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL is not set")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if database_url.startswith("postgresql://") and "sslmode" not in database_url:
    database_url += "?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
}
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

db.init_app(app)
migrate = Migrate(app, db)

app.debug = False
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard', methods = ['POST','GET'])
@login_required
def dashboard():
    projects = Projects.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html' , projects = projects)



@app.route('/new_project', methods = ['GET','POST'])
@login_required
def new_project():
    if request.method == "POST":
        project = Projects(
            title = request.form.get('title'),
            description = request.form.get('description', 'No Description'),
            status = 'Active',
            user_id = current_user.id
        )
        db.session.add(project)
        db.session.commit()
        return redirect('/dashboard')
    return render_template('new_project.html')
    

@app.route('/work_sessions/<int:project_id>')
@login_required
def work_sessions(project_id):

    project = Projects.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()


    ( 
        sessions ,
        project_id, 
        total_minutes, 
        total_sessions, 
        avg_session,
        insights,
        outcome_exists ) = insights_analyzer(project.id, db, WorkSession) 

    return render_template('project_sessions.html',
        title = project.title,
        sessions = sessions, project_id = project.id,
        total_time_spent = total_minutes,
        total_sessions = total_sessions,
        avg_session = avg_session,
        insights = insights,
        outcome_exists = outcome_exists,
        )

@app.route('/projects/<int:project_id>/new_session', methods = ['GET','POST'])
@login_required
def new_session(project_id):
    project = Projects.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        session_date = datetime.strptime(
            request.form["session-date"], "%Y-%m-%d"
        ).date()

        start_t = datetime.strptime(
            request.form["start_time"], "%H:%M"
        ).time()

        end_t = datetime.strptime(
            request.form["end_time"], "%H:%M"
        ).time()


        start_dt = datetime.combine(session_date, start_t)
        end_dt   = datetime.combine(session_date, end_t)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        duration_minutes = int(
            (end_dt - start_dt).total_seconds() / 60
        )
        project_session = WorkSession(
            user_id=current_user.id,
            project_id = project.id,
            session_date = session_date,
            start_time = start_dt,
            end_time = end_dt,
            duration_minutes = duration_minutes,
            work_description = request.form.get('work_description').strip(),
            outcome = request.form.get('outcome').strip()
        )
        db.session.add(project_session)
        db.session.commit()
        return redirect(url_for('work_sessions', project_id = project.id))
    return render_template('new_project_sessions.html', project_id = project.id)

@app.route('/dashboard/view/<int:project_id>')
@login_required
def view_project(project_id):
    project = Projects.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()
    return render_template('view_project.html',project = project)

@app.route('/dashboard/delete/<int:project_id>', methods = ['POST'])
@login_required
def delete_project(project_id):
    project = Projects.query.filter_by(
        id = project_id,
        user_id = current_user.id
    ).first_or_404()

    db.session.delete(project)
    db.session.commit()
    return redirect('/dashboard')


@app.route('/dashboard/edit/<int:project_id>',methods = ['GET','POST'])
@login_required
def edit_project(project_id):
    project = Projects.query.filter_by(
            id=project_id,
            user_id=current_user.id
        ).first_or_404()
    if request.method == "POST":
        project.title = request.form.get('title')
        project.description = request.form.get('description')

        allowed_statuses = ["Active", "Completed", "Stalled"]
        selected_status = request.form.get('status')

        if selected_status in allowed_statuses:
            project.status = selected_status

        db.session.commit()
        return redirect('/dashboard')
    return render_template('edit_project.html', project = project)


@app.route('/register', methods = ['GET','POST'])
def register():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('register.html', error="All fields are required")

        if Users.query.filter_by(username = username).first():
            return render_template('register.html', error = "Username already taken")
        user_success , user_msg = is_valid_username(username)
        pass_success , pass_msg = is_strong_password(password)
        if not user_success or not pass_success:
            return render_template('register.html',username_error = user_msg, password_error = pass_msg)

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        new_user = Users(username = username, password = hashed_password)

        db.session.add(new_user)
        db.session.commit()
        # return redirect(url_for('login'))
        return f"{username} | {password}"
    return render_template('register.html')


@app.route('/login', methods = ['GET','POST'])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', error="All fields are required")

        user = Users.query.filter_by(username = username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error = "Invalid username or password")
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("landing"))


@app.route('/work_sessions/edit/<int:project_id>/<int:session_id>',methods = ['GET','POST'])
@login_required
def edit_session(project_id,session_id):
    session = WorkSession.query.filter_by(
        id = session_id,
        user_id = current_user.id,
        project_id = project_id
    ).first_or_404()

    if request.method == 'POST':
        session_date = datetime.strptime(
            request.form["session-date"], "%Y-%m-%d"
        ).date()

        start_t = datetime.strptime(
            request.form["start_time"], "%H:%M"
        ).time()

        end_t = datetime.strptime(
            request.form["end_time"], "%H:%M"
        ).time()


        start_dt = datetime.combine(session_date, start_t)
        end_dt   = datetime.combine(session_date, end_t)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        duration_minutes = int(
            (end_dt - start_dt).total_seconds() / 60
        )
        session.user_id = current_user.id 
        session.project_id = project_id
        session.session_date = session_date
        session.start_time = start_dt
        session.end_time = end_dt,
        session.duration_minutes = duration_minutes
        session.work_description = request.form.get('work_description').strip()
        session.outcome = request.form.get('outcome').strip()

        db.session.commit()
        return redirect(url_for('work_sessions', project_id=project_id))
    return render_template('edit_session.html', session = session)

@app.route('/work_sessions/delete/<int:project_id>/<int:session_id>', methods = ['POST'])
@login_required
def delete_session(project_id,session_id):
    session = WorkSession.query.filter_by(
        id = session_id,
        user_id = current_user.id,
        project_id = project_id
    ).first_or_404()

    db.session.delete(session)
    db.session.commit()
    return redirect(url_for('work_sessions',project_id = project_id))


@app.before_request
def make_session_permanent():
    session.permanent = True


if __name__ == "__main__":
    app.run()
