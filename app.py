from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Case, Document, Message, TimelineEvent, FeeEntry, CaseUpdate, Notification, Payment, Lawyer, ConsultationRequest, LawyerRegion, LawyerLanguage, LawyerPracticeArea
from datetime import datetime
import os
import random

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user:
        return user
    lawyer = db.session.get(Lawyer, int(user_id))
    if lawyer:
        return lawyer
    return None

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
        current_user.state = request.form.get('state', '').strip()
        current_user.district = request.form.get('district', '').strip()
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
        session['state'] = request.form.get('state')
        session['district'] = request.form.get('district')
        fee_range = request.form.get('fee_range')
        session['fee_range'] = fee_range
        session['language'] = request.form.get('language')
        session['experience'] = request.form.get('experience')
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
    # Parse fee range
    fee_range = session.get('fee_range', '1000-2000')
    if '-' in fee_range:
        parts = fee_range.split('-')
        min_fee = int(parts[0])
        max_fee = int(parts[1])
    else:
        # "10000+" means min 10000, max very high
        min_fee = 10000
        max_fee = 1000000

    state = session.get('state', '')
    district = session.get('district', '')
    language = session.get('language', '')
    experience = session.get('experience', '')
    legal_area = session.get('legal_area', '')
    sub_type = session.get('sub_type', '')

    matching_lawyers = []
    lawyers = Lawyer.query.filter_by(is_available=True).all()

    for lawyer in lawyers:
        # Fee filter
        if not (min_fee <= lawyer.consultation_fee <= max_fee):
            continue

        # Region filter
        lawyer_districts = [r.district for r in lawyer.regions]
        lawyer_states = [r.state for r in lawyer.regions]
        if district:
            if district not in lawyer_districts:
                # Check if lawyer covers entire state
                if state not in lawyer_states:
                    continue

        # Language filter
        lawyer_langs = [l.language for l in lawyer.languages]
        if language and language not in lawyer_langs:
            continue

        # Experience filter
        if experience and lawyer.experience_level != experience:
            continue

        # Practice area filter
        if legal_area:
            lawyer_areas = [pa.area for pa in lawyer.practice_areas]
            if legal_area not in lawyer_areas:
                continue

        matching_lawyers.append(lawyer)

    session['matching_lawyer_ids'] = [l.id for l in matching_lawyers[:5]]

    if len(matching_lawyers) == 0:
        flash('No advocates found matching your criteria. Try widening your fee range or selecting a different district.', 'warning')
        return redirect(url_for('consult_issue'))

    return redirect(url_for('consult_results'))

@app.route('/consult/results')
@login_required
def consult_results():
    ids = session.get('matching_lawyer_ids', [])
    lawyers = Lawyer.query.filter(Lawyer.id.in_(ids)).all() if ids else []
    return render_template('consult_results.html', lawyers=lawyers)

@app.route('/consult/advocate-card/<int:lawyer_id>')
@login_required
def consult_advocate_card(lawyer_id):
    lawyer = Lawyer.query.get(lawyer_id)
    if not lawyer:
        return redirect(url_for('consult_results'))

    session['advocate_name'] = lawyer.name or 'Advocate'
    session['advocate_fee'] = lawyer.consultation_fee
    session['platform_fee'] = 149
    session['selected_lawyer_id'] = lawyer.id

    return render_template('consult_advocate_card.html', lawyer=lawyer)

@app.route('/consult/request', methods=['POST'])
@login_required
def consult_request():
    lawyer = Lawyer.query.get(session.get('selected_lawyer_id'))
    if not lawyer:
        flash('Please select an advocate first.', 'error')
        return redirect(url_for('consult_results'))

    session['advocate_name'] = lawyer.name or 'Advocate'
    session['advocate_fee'] = lawyer.consultation_fee
    session['platform_fee'] = 149

    # Create consultation request for the lawyer
    fee_range = session.get('fee_range', '')
    if '-' in fee_range:
        parts = fee_range.split('-')
        min_fee = int(parts[0])
        max_fee = int(parts[1])
    else:
        min_fee = 10000
        max_fee = 1000000

    cons_req = ConsultationRequest(
        lawyer_id=lawyer.id,
        client_id=current_user.id,
        legal_area=session.get('legal_area', ''),
        sub_type=session.get('sub_type', ''),
        state=session.get('state', ''),
        district=session.get('district', ''),
        description=session.get('description', ''),
        fee_range_min=min_fee,
        fee_range_max=max_fee,
        language=session.get('language', ''),
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
        lawyer_id=session.get('selected_lawyer_id'),
        advocate_name=session.get('advocate_name', 'Advocate'),
        legal_area=session.get('legal_area', ''),
        sub_type=session.get('sub_type', ''),
        city=session.get('city', ''),
        state=session.get('state', ''),
        district=session.get('district', ''),
        description=session.get('description', ''),
        advocate_fee=session.get('advocate_fee', 1200),
        platform_fee=session.get('platform_fee', 149),
        total_paid=session.get('advocate_fee', 1200) + session.get('platform_fee', 149),
        status='Active'
    )
    db.session.add(new_case)
    db.session.commit()

    event = TimelineEvent(case_id=new_case.id, event_type='Consultation', description='Consultation booked and payment received')
    db.session.add(event)

    fee1 = FeeEntry(case_id=new_case.id, description='Consultation Fee', amount=session.get('advocate_fee', 1200), status='Paid')
    fee2 = FeeEntry(case_id=new_case.id, description='Platform Fee', amount=session.get('platform_fee', 149), status='Paid')
    db.session.add(fee1)
    db.session.add(fee2)

    payment1 = Payment(user_id=current_user.id, case_id=new_case.id, amount=session.get('advocate_fee', 1200), payment_type='Consultation Fee', status='Paid')
    payment2 = Payment(user_id=current_user.id, case_id=new_case.id, amount=session.get('platform_fee', 149), payment_type='Platform Fee', status='Paid')
    db.session.add(payment1)
    db.session.add(payment2)

    notif = Notification(
        user_id=current_user.id,
        title='Case Created',
        message=f'Your case for {session.get("legal_area", "")} has been created successfully.'
    )
    db.session.add(notif)
    db.session.commit()

    for key in ['advocate_name', 'advocate_fee', 'platform_fee', 'legal_area', 'sub_type', 'state', 'district', 'fee_range', 'language', 'experience', 'description', 'selected_lawyer_id']:
        session.pop(key, None)

    return render_template('consult_confirmation.html')

# --- Engage Module Routes (Client Side) ---
# ... (keep existing my_cases, case_detail, upload_document, send_message, add_case_update, simulate_lawyer_update, profile, notifications routes unchanged)

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
    return render_template('case_detail.html', case=case, timeline=timeline, fees=fees, documents=documents, messages=messages, updates=updates)

# ... (keep remaining client routes unchanged, but ensure profile route uses current_user fields)

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
    notif = Notification(user_id=current_user.id, title='Profile Updated', message='Your profile has been updated successfully.')
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
        # Redirect to setup if profile incomplete
        if not lawyer.name or not lawyer.regions or not lawyer.languages:
            return redirect(url_for('lawyer_setup'))
        return redirect(url_for('lawyer_dashboard'))
    return render_template('lawyer_login.html')

@app.route('/lawyer/setup', methods=['GET', 'POST'])
@login_required
def lawyer_setup():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        current_user.name = request.form.get('name', '').strip()
        current_user.email = request.form.get('email', '').strip()
        current_user.bar_council_id = request.form.get('bar_council_id', '').strip()
        enrolment_year = request.form.get('enrolment_year')
        if enrolment_year:
            current_user.enrolment_year = int(enrolment_year)
        current_user.experience_level = request.form.get('experience_level', 'Junior')
        current_user.consultation_fee = int(request.form.get('consultation_fee', 1200))
        current_user.hearing_fee = int(request.form.get('hearing_fee', 5000))

        # Clear existing related data
        LawyerRegion.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerLanguage.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerPracticeArea.query.filter_by(lawyer_id=current_user.id).delete()
        db.session.flush()

        # Add regions (multiple) with requirement check
        region_states = request.form.getlist('region_state')
        region_districts = request.form.getlist('region_district')
        region_count = 0
        for i in range(len(region_states)):
            if region_states[i] and region_districts[i]:
                region = LawyerRegion(lawyer_id=current_user.id, state=region_states[i], district=region_districts[i])
                db.session.add(region)
                region_count += 1

        if region_count == 0:
            db.session.rollback()
            flash('Please add at least one region you serve.', 'danger')
            return redirect(url_for('lawyer_setup'))

        # Add languages
        langs = request.form.getlist('languages')
        for lang in langs:
            if lang:
                l = LawyerLanguage(lawyer_id=current_user.id, language=lang)
                db.session.add(l)

        # Add practice areas
        areas = request.form.getlist('areas')
        for area in areas:
            pa = LawyerPracticeArea(lawyer_id=current_user.id, area=area, sub_type='')
            db.session.add(pa)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('lawyer_dashboard'))

    return render_template('lawyer_setup.html')
    
@app.route('/lawyer/dashboard')
@login_required
def lawyer_dashboard():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('dashboard'))
    # Redirect to setup if profile not complete
    if not current_user.name or not current_user.regions or not current_user.languages:
        return redirect(url_for('lawyer_setup'))
    pending_requests = ConsultationRequest.query.filter_by(status='Pending').all()
    active_cases = Case.query.all()
    total_earnings = sum([c.total_paid for c in active_cases])
    unread_messages = Message.query.filter_by(sender='client').count()
    return render_template('lawyer_dashboard.html',
                         pending_requests=pending_requests,
                         active_cases=active_cases,
                         total_earnings=total_earnings,
                         unread_messages=unread_messages)

# ... (keep lawyer_requests, accept/decline, lawyer_cases, lawyer_case_detail, log hearing, message, upload routes unchanged except maybe adjust case retrieval)

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
    return render_template('lawyer_case_detail.html', case=case, timeline=timeline, messages=messages, documents=documents)

@app.route('/lawyer/case/<int:case_id>/log-hearing', methods=['POST'])
@login_required
def lawyer_log_hearing(case_id):
    case = Case.query.get(case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    description = request.form.get('description', 'Hearing attended')
    hearing_fee = current_user.hearing_fee if hasattr(current_user, 'hearing_fee') else 5000
    event = TimelineEvent(case_id=case_id, event_type='Hearing', description=description)
    db.session.add(event)
    fee = FeeEntry(case_id=case_id, description=description, amount=hearing_fee, status='Pending')
    db.session.add(fee)
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

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
