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
    is_lawyer = db.Column(db.Boolean, default=False)
    onboarding_complete = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    advocate_name = db.Column(db.String(100))
    legal_area = db.Column(db.String(50))
    sub_type = db.Column(db.String(50))
    city = db.Column(db.String(100))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Fee tracking
    advocate_fee = db.Column(db.Integer, default=0)
    platform_fee = db.Column(db.Integer, default=0)
    total_paid = db.Column(db.Integer, default=0)
    retainer_balance = db.Column(db.Integer, default=0)
    
    # Relationships
    documents = db.relationship('Document', backref='case', lazy=True)
    messages = db.relationship('Message', backref='case', lazy=True)
    timeline_events = db.relationship('TimelineEvent', backref='case', lazy=True)
    fee_entries = db.relationship('FeeEntry', backref='case', lazy=True)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    filename = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'), nullable=False)
    sender = db.Column(db.String(50))  # 'client' or 'lawyer'
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
    status = db.Column(db.String(20), default='Paid')  # Paid, Pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    message = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'))
    amount = db.Column(db.Integer)
    payment_type = db.Column(db.String(50))  # Consultation Fee, Hearing Fee, Platform Fee, Retainer
    status = db.Column(db.String(20), default='Paid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
