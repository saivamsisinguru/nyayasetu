from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    city = db.Column(db.String(100))
    language = db.Column(db.String(50))
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    is_lawyer = db.Column(db.Boolean, default=False)
    onboarding_complete = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cases = db.relationship('Case', backref='client', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

class Lawyer(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    bar_council_id = db.Column(db.String(50))
    enrolment_year = db.Column(db.Integer)
    experience_level = db.Column(db.String(50), default='Junior')
    consultation_fee = db.Column(db.Integer, default=1200)
    hearing_fee = db.Column(db.Integer, default=5000)
    is_verified = db.Column(db.Boolean, default=False)
    is_available = db.Column(db.Boolean, default=True)
    verification_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    consultation_requests = db.relationship('ConsultationRequest', backref='lawyer', lazy=True)
    assigned_cases = db.relationship('Case', backref='assigned_lawyer', lazy=True, foreign_keys='Case.lawyer_id')
    regions = db.relationship('LawyerRegion', backref='lawyer', lazy=True, cascade='all, delete-orphan')
    languages = db.relationship('LawyerLanguage', backref='lawyer', lazy=True, cascade='all, delete-orphan')
    practice_areas = db.relationship('LawyerPracticeArea', backref='lawyer', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('LawyerNotification', backref='lawyer', lazy=True, cascade='all, delete-orphan')

class LawyerRegion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100), nullable=False)

class LawyerLanguage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    language = db.Column(db.String(50), nullable=False)

class LawyerPracticeArea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    area = db.Column(db.String(50), nullable=False)
    sub_type = db.Column(db.String(100))

class ConsultationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    legal_area = db.Column(db.String(50))
    sub_type = db.Column(db.String(50))
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    description = db.Column(db.Text)
    fee_range_min = db.Column(db.Integer)
    fee_range_max = db.Column(db.Integer)
    language = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Pending')
    responded_at = db.Column(db.DateTime)   # <-- added for analytics
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship('User', backref='consultation_requests')

class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'))
    advocate_name = db.Column(db.String(100))
    legal_area = db.Column(db.String(50))
    sub_type = db.Column(db.String(50))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Active')
    hearing_date = db.Column(db.DateTime)              # <-- added
    next_hearing_date = db.Column(db.DateTime)         # <-- added
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    advocate_fee = db.Column(db.Integer, default=0)
    platform_fee = db.Column(db.Integer, default=0)
    total_paid = db.Column(db.Integer, default=0)
    retainer_balance = db.Column(db.Integer, default=0)

    documents = db.relationship('Document', backref='case', lazy=True)
    messages = db.relationship('Message', backref='case', lazy=True)
    timeline_events = db.relationship('TimelineEvent', backref='case', lazy=True)
    fee_entries = db.relationship('FeeEntry', backref='case', lazy=True)
    case_updates = db.relationship('CaseUpdate', backref='case', lazy=True)
    hearing_updates = db.relationship('HearingUpdate', backref='case', lazy=True, cascade='all, delete-orphan')

class HearingUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    hearing_date = db.Column(db.DateTime)
    outcome = db.Column(db.Text)
    next_hearing_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    filename = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    sender = db.Column(db.String(50))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TimelineEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    event_type = db.Column(db.String(100))
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FeeEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    description = db.Column(db.String(200))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(20), default='Paid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CaseUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    update_type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LawyerNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'))
    amount = db.Column(db.Integer)
    payment_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Paid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='payment_records')

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(300))
    working_hours = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
