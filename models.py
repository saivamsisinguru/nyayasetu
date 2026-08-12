from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100))
    city = db.Column(db.String(100))
    is_lawyer = db.Column(db.Boolean, default=False)

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
    
    def __repr__(self):
        return f'<Case {self.id}: {self.legal_area} - {self.sub_type}>'
