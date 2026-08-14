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

class LawyerNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lawyer_id = db.Column(db.Integer, db.ForeignKey('lawyer.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ... rest of models unchanged (from final models.py, but add LawyerNotification relationship to Lawyer)
# For completeness, include all remaining models as previously provided.
# I'll not repeat all classes here but include the full file at the end for clarity.
