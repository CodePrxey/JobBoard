# Websites HTML uses Bootstrap as it is easier to use than messing with css

from flask import Flask, render_template, request, redirect, url_for, flash, session
# Makes creating a login page simpler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
# Allows for passwords to be stored as hashes
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'loti-slepena-atslega'

# Path to database
DATABASE = Path(__file__).parent / 'jobboard.db'

# Get database
def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

# Create database (if doesnt exist)
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                industry TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES user (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requirements TEXT NOT NULL,
                salary INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES company (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS application (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id),
                FOREIGN KEY (job_id) REFERENCES job (id)
            )
        ''')
        
        db.commit()
        db.close()

# Call creation of database
init_db()

# Set up login logic
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, name, email, password, role):
        self.id = user_id
        self.name = name
        self.email = email
        self.password = password
        self.role = role

# User loading logic
@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM user WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    db.close()
    
    if user_data:
        return User(user_data['id'], user_data['name'], user_data['email'], 
                   user_data['password'], user_data['role'])
    return None

# Routes to all pages
# / --------------- /
# First page (the home page)
@app.route('/')
def index():
    return render_template('index.html')

# Login page with functionality to check if inputed data in form is correct to login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM user WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        db.close()
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['name'], user_data['email'], 
                       user_data['password'], user_data['role'])
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid email or password')
    return render_template('login.html')

# Sign up page with functionality to create a new user
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT * FROM user WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Email already exists')
            db.close()
            return redirect(url_for('signup'))
        
        # Create new user
        cursor.execute('''
            INSERT INTO user (name, email, password, role)
            VALUES (?, ?, ?, ?)
        ''', (name, email, generate_password_hash(password), role))
        
        db.commit()
        db.close()
        return redirect(url_for('login'))
    
    return render_template('signup.html')

# Dashboard for job seeker and employer
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'job_seeker':
        db = get_db()
        cursor = db.cursor()
        
        # Get recent jobs with application status
        cursor.execute('''
            SELECT j.*, c.name as company_name, c.location as company_location,
                   CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied
            FROM job j
            JOIN company c ON j.company_id = c.id
            LEFT JOIN application a ON j.id = a.job_id AND a.user_id = ?
            ORDER BY j.id DESC
            LIMIT 5
        ''', (current_user.id,))
        jobs = cursor.fetchall()
        
        # Get recent applications
        cursor.execute('''
            SELECT a.*, j.title as job_title, c.name as company_name
            FROM application a
            JOIN job j ON a.job_id = j.id
            JOIN company c ON j.company_id = c.id
            WHERE a.user_id = ?
            ORDER BY a.id DESC
            LIMIT 5
        ''', (current_user.id,))
        applications = cursor.fetchall()
        
        db.close()
        return render_template('job_seeker_dashboard.html', jobs=jobs, applications=applications)
    else:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
        company = cursor.fetchone()
        
        if not company:
            db.close()
            return render_template('employer_dashboard.html', company=None)
        
        # Get recent jobs
        cursor.execute('''
            SELECT j.*, c.name as company_name
            FROM job j
            JOIN company c ON j.company_id = c.id
            WHERE j.company_id = ?
            ORDER BY j.id DESC
            LIMIT 5
        ''', (company['id'],))
        jobs = cursor.fetchall()
        
        # Get recent applications
        cursor.execute('''
            SELECT a.*, j.title as job_title, c.name as company_name
            FROM application a
            JOIN job j ON a.job_id = j.id
            JOIN company c ON j.company_id = c.id
            WHERE j.company_id = ?
            ORDER BY a.id DESC
            LIMIT 5
        ''', (company['id'],))
        applications = cursor.fetchall()
        
        db.close()
        return render_template('employer_dashboard.html', company=company, jobs=jobs, applications=applications)

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Find job page functionality
@app.route('/find_jobs')
@login_required
def find_jobs():
    if current_user.role != 'job_seeker':
        return redirect(url_for('dashboard'))
    
    keyword = request.args.get('keyword', '')
    location = request.args.get('location', '')
    industry = request.args.get('industry', '')
    
    db = get_db()
    cursor = db.cursor()
    
    query = '''
        SELECT j.*, c.name as company_name, c.location, c.industry
        FROM job j
        JOIN company c ON j.company_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if keyword:
        query += ' AND (j.title LIKE ? OR j.description LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    if location:
        query += ' AND c.location LIKE ?'
        params.append(f'%{location}%')
    if industry:
        query += ' AND c.industry = ?'
        params.append(industry)
    
    query += ' ORDER BY j.id DESC'
    cursor.execute(query, params)
    jobs = cursor.fetchall()
    
    db.close()
    return render_template('find_jobs.html', jobs=jobs)

# Selection for each job
@app.route('/job/<int:job_id>')
@login_required
def job_details(job_id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT j.*, c.name as company_name, c.location, c.industry,
               CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END as has_applied
        FROM job j
        JOIN company c ON j.company_id = c.id
        LEFT JOIN application a ON j.id = a.job_id AND a.user_id = ?
        WHERE j.id = ?
    ''', (current_user.id, job_id))
    job = cursor.fetchone()
    
    if not job:
        db.close()
        flash('Job not found.')
        return redirect(url_for('find_jobs'))
    
    db.close()
    return render_template('job_details.html', job=job, has_applied=job['has_applied'])

# Application for each job
@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
def apply_job(job_id):
    if current_user.role != 'job_seeker':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT j.*, c.name as company_name, c.location, c.industry
        FROM job j
        JOIN company c ON j.company_id = c.id
        WHERE j.id = ?
    ''', (job_id,))
    job = cursor.fetchone()
    
    if request.method == 'POST':
        message = request.form.get('message', '')
        
        cursor.execute('''
            INSERT INTO application (user_id, job_id, status, message)
            VALUES (?, ?, 'applied', ?)
        ''', (current_user.id, job_id, message))
        
        db.commit()
        db.close()
        flash('Application submitted successfully!')
        return redirect(url_for('my_applications'))
    
    db.close()
    return render_template('apply_job.html', job=job)

# Applications of a job seeker
@app.route('/my_applications')
@login_required
def my_applications():
    if current_user.role != 'job_seeker':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT a.*, j.title as job_title, j.description as job_description, j.salary, c.name as company_name
        FROM application a
        JOIN job j ON a.job_id = j.id
        JOIN company c ON j.company_id = c.id
        WHERE a.user_id = ?
        ORDER BY a.id DESC
    ''', (current_user.id,))
    applications = cursor.fetchall()
    
    db.close()
    return render_template('my_applications.html', applications=applications)

# Functionality to post a job
@app.route('/post_job', methods=['GET', 'POST'])
@login_required
def post_job():
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if not company:
        db.close()
        flash('Please set up your company profile first.')
        return redirect(url_for('company_profile'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        requirements = request.form.get('requirements')
        salary = request.form.get('salary')
        
        if not all([title, description, requirements, salary]):
            flash('Please fill in all fields.')
            return redirect(url_for('post_job'))
        
        try:
            salary = int(salary)
            if salary <= 0:
                flash('Salary must be a positive number.')
                return redirect(url_for('post_job'))
        except ValueError:
            flash('Salary must be a valid number.')
            return redirect(url_for('post_job'))
        
        cursor.execute('''
            INSERT INTO job (title, description, requirements, salary, company_id, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (title, description, requirements, salary, company['id']))
        
        db.commit()
        db.close()
        flash('Job posted successfully!')
        return redirect(url_for('my_listings'))
    
    db.close()
    return render_template('post_job.html')

# Company profile page
@app.route('/company_profile', methods=['GET', 'POST'])
@login_required
def company_profile():
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if request.method == 'POST':
        if company:
            cursor.execute('''
                UPDATE company
                SET name = ?, location = ?, industry = ?
                WHERE id = ?
            ''', (request.form.get('name'), request.form.get('location'),
                  request.form.get('industry'), company['id']))
        else:
            cursor.execute('''
                INSERT INTO company (name, location, industry, owner_id)
                VALUES (?, ?, ?, ?)
            ''', (request.form.get('name'), request.form.get('location'),
                  request.form.get('industry'), current_user.id))
        
        db.commit()
        db.close()
        flash('Company profile updated successfully!')
        return redirect(url_for('dashboard'))
    
    db.close()
    return render_template('company_profile.html', company=company)

# Job applications for the employer
@app.route('/job_applications/<int:job_id>')
@login_required
def job_applications(job_id):
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    # Get the job and its company
    cursor.execute('''
        SELECT j.*, c.name as company_name, c.owner_id
        FROM job j
        JOIN company c ON j.company_id = c.id
        WHERE j.id = ?
    ''', (job_id,))
    job = cursor.fetchone()
    
    # Check if the current user owns the company
    if not job or job['owner_id'] != current_user.id:
        db.close()
        return redirect(url_for('dashboard'))
    
    # Get applications for this job
    cursor.execute('''
        SELECT a.*, u.name as applicant_name
        FROM application a
        JOIN user u ON a.user_id = u.id
        WHERE a.job_id = ?
    ''', (job_id,))
    applications = cursor.fetchall()
    
    db.close()
    return render_template('job_applications.html', job=job, applications=applications)

# Update each application functionality
@app.route('/update_application_status/<int:application_id>', methods=['POST'])
@login_required
def update_application_status(application_id):
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT a.*, j.company_id
        FROM application a
        JOIN job j ON a.job_id = j.id
        WHERE a.id = ?
    ''', (application_id,))
    application = cursor.fetchone()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if not company or application['company_id'] != company['id']:
        db.close()
        return redirect(url_for('dashboard'))
    
    new_status = request.form.get('status')
    if new_status in ['applied', 'interviewing', 'hired']:
        cursor.execute('''
            UPDATE application
            SET status = ?
            WHERE id = ?
        ''', (new_status, application_id))
        
        db.commit()
        flash('Application status updated successfully!')
    
    db.close()
    return redirect(url_for('job_applications', job_id=application['job_id']))

# Job deletion functionality
@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM job WHERE id = ?', (job_id,))
    job = cursor.fetchone()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if not company or job['company_id'] != company['id']:
        flash('You do not have permission to delete this job')
        db.close()
        return redirect(url_for('dashboard'))
    
    try:
        # First, delete all applications for this job
        cursor.execute('DELETE FROM application WHERE job_id = ?', (job_id,))
        # Then delete the job
        cursor.execute('DELETE FROM job WHERE id = ?', (job_id,))
        db.commit()
        flash('Job posting deleted successfully!')
    except Exception as e:
        db.rollback()
        flash('Error deleting job posting. Please try again.')
    
    db.close()
    return redirect(url_for('my_listings'))

# Listing page for employer
@app.route('/my_listings')
@login_required
def my_listings():
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if not company:
        flash('Please set up your company profile first')
        db.close()
        return redirect(url_for('company_profile'))
    
    cursor.execute('''
        SELECT j.*, c.name as company_name, c.location, c.industry
        FROM job j
        JOIN company c ON j.company_id = c.id
        WHERE j.company_id = ?
        ORDER BY j.id DESC
    ''', (company['id'],))
    jobs = cursor.fetchall()
    
    db.close()
    return render_template('my_listings.html', jobs=jobs)

# Job editing functionality for the employer
@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    if current_user.role != 'employer':
        return redirect(url_for('dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM job WHERE id = ?', (job_id,))
    job = cursor.fetchone()
    
    cursor.execute('SELECT * FROM company WHERE owner_id = ?', (current_user.id,))
    company = cursor.fetchone()
    
    if not company or job['company_id'] != company['id']:
        flash('You do not have permission to edit this job')
        db.close()
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        cursor.execute('''
            UPDATE job
            SET title = ?, description = ?, requirements = ?, salary = ?
            WHERE id = ?
        ''', (request.form.get('title'), request.form.get('description'),
              request.form.get('requirements'), request.form.get('salary'), job_id))
        
        db.commit()
        db.close()
        flash('Job updated successfully!')
        return redirect(url_for('my_listings'))
    
    db.close()
    return render_template('edit_job.html', job=job)

# Profile of employer or job seeker
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM user WHERE id = ?', (current_user.id,))
        user = cursor.fetchone()
        
        if not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect')
            db.close()
            return redirect(url_for('profile'))
        
        if new_password:
            cursor.execute('''
                UPDATE user
                SET name = ?, email = ?, password = ?
                WHERE id = ?
            ''', (name, email, generate_password_hash(new_password), current_user.id))
        else:
            cursor.execute('''
                UPDATE user
                SET name = ?, email = ?
                WHERE id = ?
            ''', (name, email, current_user.id))
        
        db.commit()
        db.close()
        flash('Profile updated successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('profile.html')

if __name__ == '__main__':
    app.run(debug=True) 