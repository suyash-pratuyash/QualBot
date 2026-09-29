"""Admin analytics queries."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.domain.models import Conversation, Lead

def overview(db: Session):
    total_conversations=db.scalar(select(func.count()).select_from(Conversation)) or 0
    total_leads=db.scalar(select(func.count()).select_from(Lead)) or 0
    qualified=db.scalar(select(func.count()).select_from(Lead).where(Lead.qualification_status=="qualified")) or 0
    high=db.scalar(select(func.count()).select_from(Lead).where(Lead.qualification_status=="high_intent")) or 0
    avg=float(db.scalar(select(func.avg(Lead.score))) or 0)
    converted=db.scalar(select(func.count()).select_from(Lead).where(Lead.operational_status=="converted")) or 0
    rate=(converted/total_leads*100) if total_leads else 0
    return {"total_conversations":total_conversations,"total_leads":total_leads,"qualified_leads":qualified,"high_intent_leads":high,"average_lead_score":round(avg,1),"conversion_rate":round(rate,1)}
