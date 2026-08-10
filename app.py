from flask import Flask, render_template, redirect, url_for, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        user = User.query.filter_by(phone=phone).first()
        if not user:
            user = User(phone=phone, name='New User')
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/consult/issue', methods=['GET', 'POST'])
@login_required
def consult_issue():
    if request.method == 'POST':
        session['legal_area'] = request.form.get('legal_area')
        session['sub_type'] = request.form.get('sub_type')
        session['city'] = request.form.get('city')
        return redirect(url_for('consult_context'))
    return render_template('consult_issue.html')

@app.route('/consult/context', methods=['GET', 'POST'])
@login_required
def consult_context():
    if request.method == 'POST':
        session['description'] = request.form.get('description')
        return redirect(url_for('dashboard'))
    return render_template('consult_context.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Run ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
