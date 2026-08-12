from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Case, Document, Message, TimelineEvent, FeeEntry
from datetime import datetime
import os

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

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
            user = User(phone=phone)
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        
        # Check if onboarding is complete
        if not user.onboarding_complete:
            return redirect(url_for('onboarding'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- Consult Module Routes ---

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
        return redirect(url_for('consult_matching'))
    return render_template('consult_context.html')

@app.route('/consult/matching')
@login_required
def consult_matching():
    return render_template('consult_matching.html')

@app.route('/consult/advocate-card')
@login_required
def consult_advocate_card():
    advocate = {
        'name': 'Adv. Priya Menon',
        'bar_council': 'Bar Council of Karnataka',
        'enrolment_year': 2012,
        'courts': 'High Court, Family Court',
        'languages': 'Kannada, English, Hindi',
        'first_slot': 'Today, 7:30 PM (30 min)',
        'fee': 1200
    }
    return render_template('consult_advocate_card.html', advocate=advocate)

@app.route('/consult/request', methods=['POST'])
@login_required
def consult_request():
    session['advocate_name'] = 'Adv. Priya Menon'
    session['advocate_fee'] = 1200
    session['platform_fee'] = 149
    return render_template('consult_request_sent.html')

@app.route('/consult/payment')
@login_required
def consult_payment():
    advocate_name = session.get('advocate_name')
    if not advocate_name:
        return redirect(url_for('dashboard'))
    advocate_fee = session.get('advocate_fee', 1200)
    platform_fee = session.get('platform_fee', 149)
    total = advocate_fee + platform_fee
    return render_template('consult_payment.html',
                         advocate_name=advocate_name,
                         advocate_fee=advocate_fee,
                         platform_fee=platform_fee,
                         total=total)

@app.route('/consult/confirmation', methods=['POST'])
@login_required
def consult_confirmation():
    new_case = Case(
        user_id=current_user.id,
        advocate_name=session.get('advocate_name', 'Adv. Priya Menon'),
        legal_area=session.get('legal_area', ''),
        sub_type=session.get('sub_type', ''),
        city=session.get('city', ''),
        description=session.get('description', ''),
        advocate_fee=session.get('advocate_fee', 1200),
        platform_fee=session.get('platform_fee', 149),
        total_paid=session.get('advocate_fee', 1200) + session.get('platform_fee', 149),
        status='Active'
    )
    db.session.add(new_case)
    db.session.commit()
    
    # Add initial timeline event
    event = TimelineEvent(
        case_id=new_case.id,
        event_type='Consultation',
        description='Consultation booked and payment received'
    )
    db.session.add(event)
    
    # Add fee entries
    fee1 = FeeEntry(
        case_id=new_case.id,
        description='Consultation Fee',
        amount=session.get('advocate_fee', 1200),
        status='Paid'
    )
    fee2 = FeeEntry(
        case_id=new_case.id,
        description='Platform Fee',
        amount=session.get('platform_fee', 149),
        status='Paid'
    )
    db.session.add(fee1)
    db.session.add(fee2)
    db.session.commit()
    
    # Clear consultation session data
    for key in ['advocate_name', 'advocate_fee', 'platform_fee', 'legal_area', 'sub_type', 'city', 'description']:
        session.pop(key, None)
    
    return render_template('consult_confirmation.html')

# --- Engage Module Routes ---

@app.route('/my-cases')
@login_required
def my_cases():
    cases = Case.query.filter_by(user_id=current_user.id).order_by(Case.created_at.desc()).all()
    return render_template('my_cases.html', cases=cases)

@app.route('/case/<int:case_id>')
@login_required
def case_detail(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    timeline = TimelineEvent.query.filter_by(case_id=case.id).order_by(TimelineEvent.created_at.desc()).all()
    fees = FeeEntry.query.filter_by(case_id=case.id).order_by(FeeEntry.created_at.desc()).all()
    documents = Document.query.filter_by(case_id=case.id).order_by(Document.uploaded_at.desc()).all()
    messages = Message.query.filter_by(case_id=case.id).order_by(Message.created_at.asc()).all()
    
    return render_template('case_detail.html', 
                         case=case, 
                         timeline=timeline, 
                         fees=fees, 
                         documents=documents,
                         messages=messages)

# Document Upload
@app.route('/case/<int:case_id>/upload', methods=['POST'])
@login_required
def upload_document(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    if 'document' in request.files:
        file = request.files['document']
        if file.filename:
            # Create upload folder if not exists
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(case_id))
            os.makedirs(upload_folder, exist_ok=True)
            
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            doc = Document(
                case_id=case_id,
                filename=file.filename,
                file_path=file_path
            )
            db.session.add(doc)
            db.session.commit()
            
            flash('Document uploaded successfully!', 'success')
    
    return redirect(url_for('case_detail', case_id=case_id))

# Send Message
@app.route('/case/<int:case_id>/message', methods=['POST'])
@login_required
def send_message(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    content = request.form.get('message', '').strip()
    if content:
        msg = Message(
            case_id=case_id,
            sender='client',
            content=content
        )
        db.session.add(msg)
        db.session.commit()
    
    return redirect(url_for('case_detail', case_id=case_id))

# Lawyer: Log Hearing (simulated)
@app.route('/case/<int:case_id>/log-hearing', methods=['POST'])
@login_required
def log_hearing(case_id):
    # In real app, check if current_user.is_lawyer
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('my_cases'))
    
    hearing_fee = 5000  # Default hearing fee
    description = request.form.get('description', 'Hearing attended')
    
    # Add timeline event
    event = TimelineEvent(
        case_id=case_id,
        event_type='Hearing',
        description=description
    )
    db.session.add(event)
    
    # Add fee entry
    fee = FeeEntry(
        case_id=case_id,
        description=description,
        amount=hearing_fee,
        status='Pending'
    )
    db.session.add(fee)
    db.session.commit()
    
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# --- Run ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
