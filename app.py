from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import (db, User, Lawyer, Admin, Case, Document, Message, TimelineEvent,
                    FeeEntry, CaseUpdate, Notification, Payment, ConsultationRequest,
                    LawyerRegion, LawyerLanguage, LawyerPracticeArea,
                    ContactDetails, ContactMessage, LawyerNotification, HearingUpdate)
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
    user_type = session.get('user_type', 'client')
    if user_type == 'lawyer':
        return db.session.get(Lawyer, int(user_id))
    elif user_type == 'admin':
        return db.session.get(Admin, int(user_id))
    else:
        return db.session.get(User, int(user_id))

# ---------- General Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    contact = ContactDetails.query.first()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if name and email and subject and message:
            msg = ContactMessage(name=name, email=email, phone=phone, subject=subject, message=message)
            db.session.add(msg)
            db.session.commit()
            flash('Your message has been sent. We will get back to you soon.', 'success')
            return redirect(url_for('contact_us'))
    return render_template('contact_us.html', contact=contact)

# ---------- Client Auth ----------
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
        session['user_type'] = 'client'
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    return render_template('dashboard.html')

# ---------- Client Consult Flow ----------
@app.route('/consult/issue', methods=['GET', 'POST'])
@login_required
def consult_issue():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    if request.method == 'POST':
        session['legal_area'] = request.form.get('legal_area')
        session['sub_type'] = request.form.get('sub_type')
        session['state'] = request.form.get('state')
        session['district'] = request.form.get('district')
        session['fee_range'] = request.form.get('fee_range')
        session['language'] = request.form.get('language')
        session['experience'] = request.form.get('experience')
        return redirect(url_for('consult_context'))
    return render_template('consult_issue.html')

@app.route('/consult/context', methods=['GET', 'POST'])
@login_required
def consult_context():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    if request.method == 'POST':
        session['description'] = request.form.get('description')
        return redirect(url_for('consult_matching'))
    return render_template('consult_context.html')

@app.route('/consult/matching')
@login_required
def consult_matching():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    fee_range = session.get('fee_range', '1000-2000')
    if '-' in fee_range:
        parts = fee_range.split('-')
        min_fee = int(parts[0])
        max_fee = int(parts[1])
    else:
        min_fee = 10000
        max_fee = 1000000

    state = session.get('state', '')
    district = session.get('district', '')
    language = session.get('language', '')
    experience = session.get('experience', '')
    legal_area = session.get('legal_area', '')

    matching_lawyers = []
    lawyers = Lawyer.query.filter_by(is_available=True, verification_status='verified').all()

    for lawyer in lawyers:
        if not (min_fee <= lawyer.consultation_fee <= max_fee):
            continue
        lawyer_districts = [r.district for r in lawyer.regions]
        lawyer_states = [r.state for r in lawyer.regions]
        if district:
            if district not in lawyer_districts and state not in lawyer_states:
                continue
        lawyer_langs = [l.language for l in lawyer.languages]
        if language and language not in lawyer_langs:
            continue
        if experience and lawyer.experience_level != experience:
            continue
        lawyer_areas = [pa.area for pa in lawyer.practice_areas]
        if legal_area and legal_area not in lawyer_areas:
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    ids = session.get('matching_lawyer_ids', [])
    lawyers = Lawyer.query.filter(Lawyer.id.in_(ids)).all() if ids else []
    return render_template('consult_results.html', lawyers=lawyers)

@app.route('/consult/advocate-card/<int:lawyer_id>')
@login_required
def consult_advocate_card(lawyer_id):
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, lawyer_id)
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, session.get('selected_lawyer_id'))
    if not lawyer:
        flash('Please select an advocate first.', 'error')
        return redirect(url_for('consult_results'))

    session['advocate_name'] = lawyer.name or 'Advocate'
    session['advocate_fee'] = lawyer.consultation_fee
    session['platform_fee'] = 149

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

    # Create notification for lawyer
    notif = LawyerNotification(
        lawyer_id=lawyer.id,
        title='New Consultation Request',
        message=f'{current_user.phone} requested a consultation for {session.get("legal_area", "")}.'
    )
    db.session.add(notif)
    db.session.commit()

    return render_template('consult_request_sent.html')

@app.route('/consult/payment')
@login_required
def consult_payment():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    if not session.get('advocate_name'):
        return redirect(url_for('dashboard'))
    advocate_fee = session.get('advocate_fee', 1200)
    platform_fee = session.get('platform_fee', 149)
    total = advocate_fee + platform_fee
    return render_template('consult_payment.html',
                         advocate_name=session.get('advocate_name'),
                         advocate_fee=advocate_fee,
                         platform_fee=platform_fee,
                         total=total)

@app.route('/consult/confirmation', methods=['POST'])
@login_required
def consult_confirmation():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    advocate_name = session.get('advocate_name', 'Advocate')
    advocate_fee = session.get('advocate_fee', 1200)
    platform_fee = session.get('platform_fee', 149)
    total_paid = advocate_fee + platform_fee

    new_case = Case(
        user_id=current_user.id,
        lawyer_id=session.get('selected_lawyer_id'),
        advocate_name=advocate_name,
        legal_area=session.get('legal_area', ''),
        sub_type=session.get('sub_type', ''),
        city=session.get('city', ''),
        state=session.get('state', ''),
        district=session.get('district', ''),
        description=session.get('description', ''),
        advocate_fee=advocate_fee,
        platform_fee=platform_fee,
        total_paid=total_paid,
        status='Active'
    )
    db.session.add(new_case)
    db.session.commit()

    event = TimelineEvent(case_id=new_case.id, event_type='Consultation', description='Consultation booked and payment received')
    db.session.add(event)
    fee1 = FeeEntry(case_id=new_case.id, description='Consultation Fee', amount=advocate_fee, status='Paid')
    fee2 = FeeEntry(case_id=new_case.id, description='Platform Fee', amount=platform_fee, status='Paid')
    db.session.add(fee1)
    db.session.add(fee2)
    payment1 = Payment(user_id=current_user.id, case_id=new_case.id, amount=advocate_fee, payment_type='Consultation Fee', status='Paid')
    payment2 = Payment(user_id=current_user.id, case_id=new_case.id, amount=platform_fee, payment_type='Platform Fee', status='Paid')
    db.session.add(payment1)
    db.session.add(payment2)
    notif = Notification(user_id=current_user.id, title='Case Created', message=f'Your case for {session.get("legal_area", "")} has been created successfully.')
    db.session.add(notif)
    db.session.commit()

    for key in ['advocate_name', 'advocate_fee', 'platform_fee', 'legal_area', 'sub_type', 'state', 'district', 'fee_range', 'language', 'experience', 'description', 'selected_lawyer_id']:
        session.pop(key, None)

    return render_template('consult_confirmation.html',
                         advocate_name=advocate_name,
                         advocate_fee=advocate_fee,
                         platform_fee=platform_fee,
                         total_paid=total_paid)

# ---------- Client Engage Module ----------
@app.route('/my-cases')
@login_required
def my_cases():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    cases = Case.query.filter_by(user_id=current_user.id).order_by(Case.created_at.desc()).all()
    return render_template('my_cases.html', cases=cases)

@app.route('/my-cases/search')
@login_required
def search_cases():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    timeline = TimelineEvent.query.filter_by(case_id=case.id).order_by(TimelineEvent.created_at.desc()).all()
    fees = FeeEntry.query.filter_by(case_id=case.id).order_by(FeeEntry.created_at.desc()).all()
    documents = Document.query.filter_by(case_id=case.id).order_by(Document.uploaded_at.desc()).all()
    messages = Message.query.filter_by(case_id=case.id).order_by(Message.created_at.asc()).all()
    updates = CaseUpdate.query.filter_by(case_id=case.id).order_by(CaseUpdate.created_at.desc()).all()
    hearings = HearingUpdate.query.filter_by(case_id=case.id).order_by(HearingUpdate.created_at.desc()).all()
    return render_template('case_detail.html', case=case, timeline=timeline, fees=fees, documents=documents, messages=messages, updates=updates, hearings=hearings)

@app.route('/case/<int:case_id>/upload', methods=['POST'])
@login_required
def upload_document(case_id):
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return redirect(url_for('my_cases'))
    content = request.form.get('message', '').strip()
    if content:
        msg = Message(case_id=case_id, sender='client', content=content)
        db.session.add(msg)
        notif = Notification(user_id=current_user.id, title='Message Sent', message=f'Your message has been sent to {case.advocate_name}.')
        db.session.add(notif)
        db.session.commit()
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/case/<int:case_id>/update', methods=['POST'])
@login_required
def add_case_update(case_id):
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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
        notif = Notification(user_id=current_user.id, title=f'Case Update: {update_type}', message=title or description)
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
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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
    notif = Notification(user_id=current_user.id, title=f'Case Update: {update["type"]}', message=update['description'])
    db.session.add(notif)
    case.status = update['type']
    db.session.commit()
    flash(f'New case update: {update["title"]}', 'info')
    return redirect(url_for('case_detail', case_id=case_id))

# ---------- Client Profile & Notifications ----------
@app.route('/profile')
@login_required
def profile():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template('profile.html', payments=payments)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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

@app.route('/notifications')
@login_required
def notifications():
    if not isinstance(current_user, User):
        return redirect(url_for('index'))
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

# ---------- Lawyer Auth & Setup ----------
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
        session['user_type'] = 'lawyer'
        if not lawyer.name or not lawyer.regions or not lawyer.languages:
            return redirect(url_for('lawyer_setup'))
        elif lawyer.verification_status != 'verified':
            return redirect(url_for('lawyer_pending'))
        else:
            return redirect(url_for('lawyer_dashboard'))
    return render_template('lawyer_login.html')

@app.route('/lawyer/setup', methods=['GET', 'POST'])
@login_required
def lawyer_setup():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
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
        current_user.verification_status = 'pending'

        LawyerRegion.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerLanguage.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerPracticeArea.query.filter_by(lawyer_id=current_user.id).delete()
        db.session.flush()

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

        langs = request.form.getlist('languages')
        for lang in langs:
            if lang:
                l = LawyerLanguage(lawyer_id=current_user.id, language=lang)
                db.session.add(l)

        areas = request.form.getlist('areas')
        for area in areas:
            pa = LawyerPracticeArea(lawyer_id=current_user.id, area=area, sub_type='')
            db.session.add(pa)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('lawyer_pending'))
    return render_template('lawyer_setup.html')

@app.route('/lawyer/pending')
@login_required
def lawyer_pending():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    return render_template('lawyer_pending.html')

@app.route('/lawyer/dashboard')
@login_required
def lawyer_dashboard():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    if current_user.verification_status != 'verified':
        return redirect(url_for('lawyer_pending'))
    pending_requests = ConsultationRequest.query.filter_by(lawyer_id=current_user.id, status='Pending').all()
    active_cases = Case.query.filter_by(lawyer_id=current_user.id).all()
    total_earnings = sum([c.total_paid for c in active_cases])
    unread_messages = Message.query.filter_by(sender='client').count()
    unread_notifications = LawyerNotification.query.filter_by(lawyer_id=current_user.id, is_read=False).count()
    return render_template('lawyer_dashboard.html',
                         pending_requests=pending_requests,
                         active_cases=active_cases,
                         total_earnings=total_earnings,
                         unread_messages=unread_messages,
                         unread_notifications=unread_notifications)

@app.route('/lawyer/notifications')
@login_required
def lawyer_notifications():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    notifs = LawyerNotification.query.filter_by(lawyer_id=current_user.id).order_by(LawyerNotification.created_at.desc()).all()
    return render_template('lawyer_notifications.html', notifications=notifs)

@app.route('/lawyer/notifications/read/<int:notif_id>')
@login_required
def mark_lawyer_notification_read(notif_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    notif = db.session.get(LawyerNotification, notif_id)
    if notif and notif.lawyer_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(url_for('lawyer_notifications'))

@app.route('/lawyer/profile')
@login_required
def lawyer_profile():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    return render_template('lawyer_profile.html')

@app.route('/lawyer/profile/edit', methods=['GET', 'POST'])
@login_required
def lawyer_profile_edit():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    if request.method == 'POST':
        current_user.name = request.form.get('name', '').strip()
        current_user.email = request.form.get('email', '').strip()
        enrolment_year = request.form.get('enrolment_year')
        if enrolment_year:
            current_user.enrolment_year = int(enrolment_year)
        current_user.experience_level = request.form.get('experience_level', 'Junior')
        current_user.consultation_fee = int(request.form.get('consultation_fee', 1200))
        current_user.hearing_fee = int(request.form.get('hearing_fee', 5000))

        LawyerRegion.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerLanguage.query.filter_by(lawyer_id=current_user.id).delete()
        LawyerPracticeArea.query.filter_by(lawyer_id=current_user.id).delete()
        db.session.flush()

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
            return redirect(url_for('lawyer_profile_edit'))

        langs = request.form.getlist('languages')
        for lang in langs:
            l = LawyerLanguage(lawyer_id=current_user.id, language=lang)
            db.session.add(l)

        areas = request.form.getlist('areas')
        for area in areas:
            pa = LawyerPracticeArea(lawyer_id=current_user.id, area=area, sub_type='')
            db.session.add(pa)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('lawyer_profile'))
    return render_template('lawyer_profile_edit.html')

# ---------- Lawyer Actions ----------
@app.route('/lawyer/requests')
@login_required
def lawyer_requests():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    requests = ConsultationRequest.query.filter_by(lawyer_id=current_user.id).order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('lawyer_requests.html', requests=requests)

@app.route('/lawyer/request/<int:req_id>/accept')
@login_required
def accept_request(req_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    req = db.session.get(ConsultationRequest, req_id)
    if req:
        req.status = 'Accepted'
        req.responded_at = datetime.utcnow()
        db.session.commit()
        # Notify client
        client_notif = Notification(
            user_id=req.client_id,
            title='Request Accepted',
            message=f'Your consultation request has been accepted by {req.lawyer.name or req.lawyer.phone}.'
        )
        db.session.add(client_notif)
        db.session.commit()
        flash('Request accepted!', 'success')
    return redirect(url_for('lawyer_requests'))

@app.route('/lawyer/request/<int:req_id>/decline')
@login_required
def decline_request(req_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    req = db.session.get(ConsultationRequest, req_id)
    if req:
        req.status = 'Declined'
        req.responded_at = datetime.utcnow()
        db.session.commit()
        flash('Request declined.', 'info')
    return redirect(url_for('lawyer_requests'))

@app.route('/lawyer/cases')
@login_required
def lawyer_cases():
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    cases = Case.query.filter_by(lawyer_id=current_user.id).all()
    return render_template('lawyer_cases.html', cases=cases)

@app.route('/lawyer/case/<int:case_id>')
@login_required
def lawyer_case_detail(case_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    case = db.session.get(Case, case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    timeline = TimelineEvent.query.filter_by(case_id=case.id).order_by(TimelineEvent.created_at.desc()).all()
    messages = Message.query.filter_by(case_id=case.id).order_by(Message.created_at.asc()).all()
    documents = Document.query.filter_by(case_id=case.id).all()
    hearings = HearingUpdate.query.filter_by(case_id=case.id).order_by(HearingUpdate.created_at.desc()).all()
    return render_template('lawyer_case_detail.html', case=case, timeline=timeline, messages=messages, documents=documents, hearings=hearings)

@app.route('/lawyer/case/<int:case_id>/hearing-update', methods=['GET', 'POST'])
@login_required
def lawyer_hearing_update(case_id):
    if not isinstance(current_user, Lawyer):
        return redirect(url_for('index'))
    case = db.session.get(Case, case_id)
    if not case:
        return redirect(url_for('lawyer_cases'))
    if request.method == 'POST':
        hearing_date_str = request.form.get('hearing_date')
        outcome = request.form.get('outcome', '').strip()
        next_hearing_date_str = request.form.get('next_hearing_date')
        notes = request.form.get('notes', '').strip()
        hearing_date = None
        next_hearing_date = None
        if hearing_date_str:
            try:
                hearing_date = datetime.strptime(hearing_date_str, '%Y-%m-%dT%H:%M')
            except:
                pass
        if next_hearing_date_str:
            try:
                next_hearing_date = datetime.strptime(next_hearing_date_str, '%Y-%m-%dT%H:%M')
            except:
                pass

        # Create hearing update
        hu = HearingUpdate(
            case_id=case_id,
            lawyer_id=current_user.id,
            hearing_date=hearing_date,
            outcome=outcome,
            next_hearing_date=next_hearing_date,
            notes=notes
        )
        db.session.add(hu)

        # Update case
        case.hearing_date = hearing_date
        case.next_hearing_date = next_hearing_date
        if outcome:
            case.status = 'Hearing Updated'
        else:
            case.status = 'Hearing Completed'

        # Add timeline event
        event_desc = f'Hearing update by {current_user.name or current_user.phone}'
        if hearing_date:
            event_desc += f' on {hearing_date.strftime("%d %b %Y %H:%M")}'
        event = TimelineEvent(case_id=case_id, event_type='Hearing Update', description=event_desc)
        db.session.add(event)

        # Add fee entry (optional)
        hearing_fee = current_user.hearing_fee if current_user.hearing_fee else 5000
        fee = FeeEntry(case_id=case_id, description='Hearing Fee', amount=hearing_fee, status='Pending')
        db.session.add(fee)

        # Notify client
        client_notif = Notification(
            user_id=case.user_id,
            title='Hearing Update',
            message=f'Your advocate has provided a hearing update: {outcome[:100] if outcome else "Please check your case for details."}'
        )
        db.session.add(client_notif)

        db.session.commit()
        flash('Hearing update submitted successfully!', 'success')
        return redirect(url_for('lawyer_case_detail', case_id=case_id))
    return render_template('lawyer_hearing_update.html', case=case)

@app.route('/lawyer/case/<int:case_id>/log-hearing', methods=['POST'])
@login_required
def lawyer_log_hearing(case_id):
    # Redirect to new hearing update page
    return redirect(url_for('lawyer_hearing_update', case_id=case_id))

# Keep old message and upload routes
@app.route('/lawyer/case/<int:case_id>/message', methods=['POST'])
@login_required
def lawyer_send_message(case_id):
    case = db.session.get(Case, case_id)
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
    case = db.session.get(Case, case_id)
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
    session.clear()
    return redirect(url_for('index'))

# ---------- Admin Routes ----------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        admin = Admin.query.filter_by(phone=phone).first()
        if admin:
            login_user(admin)
            session['user_type'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Admin not found.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    total_clients = User.query.count()
    total_lawyers = Lawyer.query.count()
    total_cases = Case.query.count()
    total_payments = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).scalar()
    pending_lawyers_count = Lawyer.query.filter_by(verification_status='pending').count()
    recent_lawyers = Lawyer.query.order_by(Lawyer.created_at.desc()).limit(5).all()
    recent_cases = Case.query.order_by(Case.created_at.desc()).limit(5).all()
    return render_template('admin_dashboard.html',
                         total_clients=total_clients,
                         total_lawyers=total_lawyers,
                         total_cases=total_cases,
                         total_payments=total_payments,
                         pending_lawyers_count=pending_lawyers_count,
                         recent_lawyers=recent_lawyers,
                         recent_cases=recent_cases)

@app.route('/admin/lawyers')
@login_required
def admin_lawyers():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    lawyers = Lawyer.query.order_by(Lawyer.created_at.desc()).all()
    return render_template('admin_lawyers.html', lawyers=lawyers)

@app.route('/admin/verify/<int:lawyer_id>')
@login_required
def admin_verify_lawyer(lawyer_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, lawyer_id)
    if lawyer:
        lawyer.verification_status = 'verified'
        db.session.commit()
        flash(f'{lawyer.name} verified!', 'success')
    return redirect(url_for('admin_lawyers'))

@app.route('/admin/reject/<int:lawyer_id>')
@login_required
def admin_reject_lawyer(lawyer_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, lawyer_id)
    if lawyer:
        lawyer.verification_status = 'rejected'
        db.session.commit()
        flash(f'{lawyer.name} rejected.', 'info')
    return redirect(url_for('admin_lawyers'))

@app.route('/admin/suspend/<int:lawyer_id>')
@login_required
def admin_suspend_lawyer(lawyer_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, lawyer_id)
    if lawyer:
        lawyer.verification_status = 'suspended'
        db.session.commit()
        flash(f'{lawyer.name} suspended.', 'warning')
    return redirect(url_for('admin_lawyers'))

@app.route('/admin/unsuspend/<int:lawyer_id>')
@login_required
def admin_unsuspend_lawyer(lawyer_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    lawyer = db.session.get(Lawyer, lawyer_id)
    if lawyer:
        lawyer.verification_status = 'verified'
        db.session.commit()
        flash(f'{lawyer.name} unsuspended.', 'success')
    return redirect(url_for('admin_lawyers'))

@app.route('/admin/clients')
@login_required
def admin_clients():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    clients = User.query.order_by(User.created_at.desc()).all()
    clients_data = []
    for client in clients:
        total_paid = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(Payment.user_id == client.id).scalar()
        client.total_paid = total_paid
        clients_data.append(client)
    return render_template('admin_clients.html', clients=clients_data)

@app.route('/admin/suspend-client/<int:client_id>')
@login_required
def admin_suspend_client(client_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    client = db.session.get(User, client_id)
    if client:
        client.is_active = False
        db.session.commit()
        flash(f'{client.name or client.phone} suspended.', 'warning')
    return redirect(url_for('admin_clients'))

@app.route('/admin/unsuspend-client/<int:client_id>')
@login_required
def admin_unsuspend_client(client_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    client = db.session.get(User, client_id)
    if client:
        client.is_active = True
        db.session.commit()
        flash(f'{client.name or client.phone} unsuspended.', 'success')
    return redirect(url_for('admin_clients'))

@app.route('/admin/payments')
@login_required
def admin_payments():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    total_consultation_fees = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(Payment.payment_type == 'Consultation Fee').scalar()
    total_platform_fees = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(Payment.payment_type == 'Platform Fee').scalar()
    total_hearing_fees = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(Payment.payment_type == 'Hearing Fee').scalar()
    return render_template('admin_payments.html',
                         payments=payments,
                         total_consultation_fees=total_consultation_fees,
                         total_platform_fees=total_platform_fees,
                         total_hearing_fees=total_hearing_fees)

@app.route('/admin/requests')
@login_required
def admin_requests():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    status_filter = request.args.get('status', '')
    area_filter = request.args.get('legal_area', '')
    query = ConsultationRequest.query
    if status_filter:
        query = query.filter(ConsultationRequest.status == status_filter)
    if area_filter:
        query = query.filter(ConsultationRequest.legal_area == area_filter)
    requests = query.order_by(ConsultationRequest.created_at.desc()).all()
    return render_template('admin_requests.html', requests=requests)

@app.route('/admin/cases')
@login_required
def admin_cases():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    cases_query = Case.query
    if query:
        cases_query = cases_query.join(User, Case.user_id == User.id).filter(
            db.or_(
                User.phone.ilike(f'%{query}%'),
                Case.advocate_name.ilike(f'%{query}%'),
                Case.legal_area.ilike(f'%{query}%'),
                Case.sub_type.ilike(f'%{query}%')
            )
        )
    if status:
        cases_query = cases_query.filter(Case.status == status)
    cases = cases_query.order_by(Case.created_at.desc()).all()
    return render_template('admin_cases.html', cases=cases)

@app.route('/admin/case/<int:case_id>')
@login_required
def admin_case_detail(case_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    case = db.session.get(Case, case_id)
    if not case:
        return redirect(url_for('admin_cases'))
    timeline = TimelineEvent.query.filter_by(case_id=case.id).order_by(TimelineEvent.created_at.desc()).all()
    fees = FeeEntry.query.filter_by(case_id=case.id).order_by(FeeEntry.created_at.desc()).all()
    documents = Document.query.filter_by(case_id=case.id).order_by(Document.uploaded_at.desc()).all()
    messages = Message.query.filter_by(case_id=case.id).order_by(Message.created_at.asc()).all()
    return render_template('admin_case_detail.html',
                         case=case,
                         timeline=timeline,
                         fees=fees,
                         documents=documents,
                         messages=messages)

@app.route('/admin/contact', methods=['GET', 'POST'])
@login_required
def admin_contact():
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    contact = ContactDetails.query.first()
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        working_hours = request.form.get('working_hours', '').strip()
        if not contact:
            contact = ContactDetails(phone=phone, email=email, address=address, working_hours=working_hours)
            db.session.add(contact)
        else:
            contact.phone = phone
            contact.email = email
            contact.address = address
            contact.working_hours = working_hours
        db.session.commit()
        flash('Contact details updated.', 'success')
        return redirect(url_for('admin_contact'))
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin_contact.html', contact=contact, messages=messages)

@app.route('/admin/message/read/<int:msg_id>')
@login_required
def admin_mark_message_read(msg_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    msg = db.session.get(ContactMessage, msg_id)
    if msg:
        msg.is_read = True
        db.session.commit()
    return redirect(url_for('admin_contact'))

@app.route('/admin/message/delete/<int:msg_id>')
@login_required
def admin_delete_message(msg_id):
    if not isinstance(current_user, Admin):
        return redirect(url_for('index'))
    msg = db.session.get(ContactMessage, msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
    return redirect(url_for('admin_contact'))

@app.route('/admin/logout')
def admin_logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# ---------- Logout ----------
@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('index'))

# ---------- Run ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(phone='9999999999').first():
            admin = Admin(phone='9999999999', name='NyayaSetu Admin')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0')
