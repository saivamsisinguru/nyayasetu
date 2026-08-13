from app import app, db
from models import (
    User, Lawyer, Admin, Case, Document, Message, TimelineEvent,
    FeeEntry, CaseUpdate, Notification, Payment, ConsultationRequest,
    LawyerRegion, LawyerLanguage, LawyerPracticeArea
)

with app.app_context():
    # Delete dependent tables first (if not already cascading)
    ConsultationRequest.query.delete()
    Notification.query.delete()
    Payment.query.delete()
    FeeEntry.query.delete()
    TimelineEvent.query.delete()
    CaseUpdate.query.delete()
    Message.query.delete()
    Document.query.delete()
    Case.query.delete()

    # Delete lawyer‑related data
    LawyerRegion.query.delete()
    LawyerLanguage.query.delete()
    LawyerPracticeArea.query.delete()
    Lawyer.query.delete()

    # Delete client users
    User.query.delete()

    # Keep Admin records (do not delete)

    db.session.commit()
    print("✅ Deleted all test clients and advocates. Admin data preserved.")
