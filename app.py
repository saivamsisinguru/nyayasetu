from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Case, Document, Message, TimelineEvent, FeeEntry, CaseUpdate, Notification, Payment
from datetime import datetime
import os
import random
from models import db, User, Case, Document, Message, TimelineEvent, FeeEntry, CaseUpdate, Notification, Payment, Lawyer, ConsultationRequest

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
        
        if not user.onboarding_complete:
            return redirect(url_for('onboarding'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    if current_user.onboarding_complete:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        current_user.name = request.form.get('name', '').strip()
        current_user.email = request.form.get('email', '').strip()
        current_user.city = request.form.get('city', '').strip()
        current_user.language = request.form.get('language', '').strip()
        current_user.onboarding_complete = True
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    return render_template('onboarding.html')

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
    
    # Create consultation request for the lawyer
    lawyer = Lawyer.query.first()
    if lawyer:
        cons_req = ConsultationRequest(
            lawyer_id=lawyer.id,
            client_id=current_user.id,
            legal_area=session.get('legal_area', ''),
            sub_type=session.get('sub_type', ''),
            city=session.get('city', ''),
            description=session.get('description', ''),
            status='Pending'
        )
        db.session.add(cons_req)
        db.session.commit()
    
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
    fee1 = FeeEntry(case_id=new_case.id, description='Consultation Fee', amount=session.get('advocate_fee', 1200), status='Paid')
    fee2 = FeeEntry(case_id=new_case.id, description='Platform Fee', amount=session.get('platform_fee', 149), status='Paid')
    db.session.add(fee1)
    db.session.add(fee2)
    
    # Add payment records
    payment1 = Payment(user_id=current_user.id, case_id=new_case.id, amount=session.get('advocate_fee', 1200), payment_type='Consultation Fee', status='Paid')
    payment2 = Payment(user_id=current_user.id, case_id=new_case.id, amount=session.get('platform_fee', 149), payment_type='Platform Fee', status='Paid')
    db.session.add(payment1)
    db.session.add(payment2)
    
    # Add notification
    notif = Notification(
        user_id=current_user.id,
        title='Case Created',
        message=f'Your case for {session.get("legal_area", "")} has been created successfully.'
    )
    db.session.add(notif)
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

@app.route('/my-cases/search')
@login_required
def search_cases():
    query = request.args.get('q', '').strip()
    if query:
        cases = Case.query.filter(
            Case.user_id == current_user.id,
            db.or_(
                Case.legal_area.ilike(f'%{query}%'),
                Case.sub_type.ilike(f'%{query}%'),
                Case.advocate_name.ilike(f'%{query}%'),
                Case.city.ilike(f'%{query}%')
            )
        ).order_by(Case.created_at.desc()).all()
    else:
        cases = Case.query.filter_by(user_id=current_user.id).order_by(Case.created_at.desc()).all()
    return render_template('my_cases.html', cases=cases, search_query=query)

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
    updates = CaseUpdate.query.filter_by(case_id=case.id).order_by(CaseUpdate.created_at.desc()).all()
    
    return render_template('case_detail.html', 
                         case=case, 
                         timeline=timeline, 
                         fees=fees, 
                         documents=documents,
                         messages=messages,
                         updates=updates)

@app.route('/case/<int:case_id>/upload', methods=['POST'])
@login_required
def upload_document(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    if 'document' in request.files:
        file = request.files['document']
        if file.filename:
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(case_id))
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            doc = Document(case_id=case_id, filename=file.filename, file_path=file_path)
            db.session.add(doc)
            db.session.commit()
            
            flash('Document uploaded successfully!', 'success')
    
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/case/<int:case_id>/message', methods=['POST'])
@login_required
def send_message(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    content = request.form.get('message', '').strip()
    if content:
        msg = Message(case_id=case_id, sender='client', content=content)
        db.session.add(msg)
        
        notif = Notification(
            user_id=current_user.id,
            title='Message Sent',
            message=f'Your message has been sent to {case.advocate_name}.'
        )
        db.session.add(notif)
        db.session.commit()
    
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/case/<int:case_id>/update', methods=['POST'])
@login_required
def add_case_update(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    update_type = request.form.get('update_type', 'Note')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    if title or description:
        update = CaseUpdate(case_id=case_id, update_type=update_type, title=title, description=description)
        db.session.add(update)
        
        event = TimelineEvent(case_id=case_id, event_type=update_type, description=title or description)
        db.session.add(event)
        
        notif = Notification(
            user_id=current_user.id,
            title=f'Case Update: {update_type}',
            message=title or description
        )
        db.session.add(notif)
        
        if update_type == 'Hearing':
            case.status = 'Hearing Scheduled'
        elif update_type == 'Order':
            case.status = 'Order Received'
        elif update_type == 'Resolved':
            case.status = 'Resolved'
        
        db.session.commit()
        flash('Case updated successfully!', 'success')
    
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/case/<int:case_id>/simulate-lawyer-update')
@login_required
def simulate_lawyer_update(case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    
    updates = [
        {'type': 'Hearing', 'title': 'Hearing Scheduled', 'description': 'Next hearing scheduled for 25 Aug 2026 at City Civil Court.'},
        {'type': 'Filing', 'title': 'Additional Documents Filed', 'description': 'Affidavit and supporting documents filed with the court.'},
        {'type': 'Order', 'title': 'Court Order Received', 'description': 'The court has directed the respondent to file a reply within 2 weeks.'},
        {'type': 'Note', 'title': 'Case Review', 'description': 'Advocate reviewed the case and prepared next steps.'}
    ]
    
    update = random.choice(updates)
    
    case_update = CaseUpdate(case_id=case_id, update_type=update['type'], title=update['title'], description=update['description'])
    db.session.add(case_update)
    
    event = TimelineEvent(case_id=case_id, event_type=update['type'], description=update['title'])
    db.session.add(event)
    
    notif = Notification(
        user_id=current_user.id,
        title=f'Case Update: {update["type"]}',
        message=update['description']
    )
    db.session.add(notif)
    
    case.status = update['type']
    db.session.commit()
    
    flash(f'New case update: {update["title"]}', 'info')
    return redirect(url_for('case_detail', case_id=case_id))

# --- Profile Routes ---

@app.route('/profile')
@login_required
def profile():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template('profile.html', payments=payments)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    current_user.name = request.form.get('name', '').strip()
    current_user.email = request.form.get('email', '').strip()
    current_user.city = request.form.get('city', '').strip()
    current_user.language = request.form.get('language', '').strip()
    db.session.commit()
    
    notif = Notification(
        user_id=current_user.id,
        title='Profile Updated',
        message='Your profile has been updated successfully.'
    )
    db.session.add(notif)
    db.session.commit()
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

# --- Notifications Routes ---

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifs)

@app.route('/notifications/read/<int:notif_id>')
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if notif:
        notif.is_read = True
        db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# --- Lawyer Routes ---

@app.route('/lawyer/login', methods=['GET', 'POST'])
def lawyer_login():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        lawyer = Lawyer.query.filter_by(phone=phone).first()
        if not lawyer:
            lawyer = Lawyer(phone=phone, name='New Lawyer')
            db.session.add(lawyer)
            db.session.commit()
        login_user(lawyer)
        return redirect(url_for('lawyer_dashboard'))
    return render_template('lawyer_login.html')

@app.route('/lawyer/dashboard')
@login_required
def lawyer_dashboard():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    
    pending_requests = ConsultationRequest.query.filter_by(status='Pending').all()
    active_cases = Case.query.all()
    total_earnings = sum([c.total_paid for c in active_cases])
    unread_messages = Message.query.filter_by(sender='client').count()
    
    return render_template('lawyer_dashboard.html',
                         pending_requests=pending_requests,
                         active_cases=active_cases,
                         total_earnings=total_earnings,
                         unread_messages=unread_messages)

@app.route('/lawyer/requests')
@login_required
def lawyer_requests():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    requests = ConsultationRequest.query.filter_by(lawyer_id=current_user.id).order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('lawyer_requests.html', requests=requests)

@app.route('/lawyer/request/<int:req_id>/accept')
@login_required
def accept_request(req_id):
    req = ConsultationRequest.query.get(req_id)
    if req:
        req.status = 'Accepted'
        db.session.commit()
        flash('Request accepted!', 'success')
    return redirect(url_for('lawyer_requests'))

@app.route('/lawyer/request/<int:req_id>/decline')
@login_required
def decline_request(req_id):
    req = ConsultationRequest.query.get(req_id)
    if req:
        req.status = 'Declined'
        db.session.commit()
        flash('Request declined.', 'info')
    return redirect(url_for('lawyer_requests'))

@app.route('/lawyer/cases')
@login_required
def lawyer_cases():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    cases = Case.query.all()
    return render_template('lawyer_cases.html', cases=cases)

@app.route('/lawyer/case/<int:case_id>')
@login_required
def lawyer_case_detail(case_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    
    timeline = TimelineEvent.query.filter_by(case_id=case.id).order_by(TimelineEvent.created_at.desc()).all()
    messages = Message.query.filter_by(case_id=case.id).order_by(Message.created_at.asc()).all()
    documents = Document.query.filter_by(case_id=case.id).all()
    
    return render_template('lawyer_case_detail.html',
                         case=case, timeline=timeline, messages=messages, documents=documents)

@app.route('/lawyer/case/<int:case_id>/log-hearing', methods=['POST'])
@login_required
def lawyer_log_hearing(case_id):
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    
    description = request.form.get('description', 'Hearing attended')
    hearing_fee = current_user.hearing_fee if hasattr(current_user, 'hearing_fee') else 5000
    
    # Add timeline event
    event = TimelineEvent(case_id=case_id, event_type='Hearing', description=description)
    db.session.add(event)
    
    # Add fee entry
    fee = FeeEntry(case_id=case_id, description=description, amount=hearing_fee, status='Pending')
    db.session.add(fee)
    
    # Update case status
    case.status = 'Hearing Completed'
    db.session.commit()
    
    flash(f'Hearing logged. Fee of ₹{hearing_fee} added to client ledger.', 'success')
    return redirect(url_for('lawyer_case_detail', case_id=case_id))

@app.route('/lawyer/case/<int:case_id>/message', methods=['POST'])
@login_required
def lawyer_send_message(case_id):
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    
    content = request.form.get('message', '').strip()
    if content:
        msg = Message(case_id=case_id, sender='lawyer', content=content)
        db.session.add(msg)
        db.session.commit()
    
    return redirect(url_for('lawyer_case_detail', case_id=case_id))

@app.route('/lawyer/case/<int:case_id>/upload', methods=['POST'])
@login_required
def lawyer_upload_document(case_id):
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    
    if 'document' in request.files:
        file = request.files['document']
        if file.filename:
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(case_id))
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            doc = Document(case_id=case_id, filename=file.filename, file_path=file_path)
            db.session.add(doc)
            db.session.commit()
            flash('Document uploaded!', 'success')
    
    return redirect(url_for('lawyer_case_detail', case_id=case_id))

@app.route('/lawyer/logout')
def lawyer_logout():
    logout_user()
    return redirect(url_for('index'))

# --- Run ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
