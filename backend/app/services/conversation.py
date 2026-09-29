"""Application service for conversation processing."""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.enums import MessageRole,RoutingActionStatus,RoutingActionType
from app.domain.models import Conversation,Message,Lead,BANTState,LeadScoreHistory,RoutingAction
from app.services.extraction import Extraction,extract
from app.services.scoring import score_bant
def _merge(b:BANTState,e:Extraction,message:str):
    updated=[]
    fields=[("budget_status","budget_confidence","budget_evidence",e.budget_status,e.budget_confidence,e.budget_evidence),("authority_level","authority_confidence","authority_evidence",e.authority_level,e.authority_confidence,e.authority_evidence),("need_clarity","need_confidence","need_evidence",e.need_clarity,e.need_confidence,e.need_evidence),("timeline_urgency","timeline_confidence","timeline_evidence",e.timeline_urgency,e.timeline_confidence,e.timeline_evidence)]
    names={"budget_status":"budget","authority_level":"authority","need_clarity":"need","timeline_urgency":"timeline"}
    for vf,cf,ef,value,conf,evidence in fields:
        if value is not None and value!="unknown":
            current=getattr(b,vf); current_conf=getattr(b,cf)
            if current=="unknown" or current_conf is None or conf is None or conf>=current_conf:
                if current!=value:updated.append(names[vf])
                setattr(b,vf,value); setattr(b,cf,conf); setattr(b,ef,evidence or message)
    if e.budget_amount is not None:b.budget_amount=e.budget_amount; b.budget_currency=e.budget_currency
    if e.need_summary:b.need_summary=e.need_summary
    return sorted(set(updated))
def _lead(conversation:Conversation,db:Session):
    if conversation.lead:return conversation.lead
    lead=Lead(conversation_id=conversation.id); lead.bant_state=BANTState(lead_id=lead.id); db.add(lead); db.flush(); return lead
def _assistant(b:BANTState,status:str)->str:
    missing=[]
    if b.budget_status=="unknown":missing.append("budget")
    if b.authority_level=="unknown":missing.append("who makes the decision")
    if b.need_clarity=="unknown":missing.append("what you need to solve")
    if b.timeline_urgency=="unknown":missing.append("timeline")
    if status=="high_intent":return "Thanks — I have enough context to route this as a high-intent lead. You can book a meeting from the option shown below."
    if missing:return "Thanks. To make this useful, could you share your "+", ".join(missing[:2])+"?"
    return "Thanks. I have the main qualification details. I can help with the next step."
async def process_message(db:Session,conversation:Conversation,text:str):
    visitor=Message(conversation_id=conversation.id,role=MessageRole.VISITOR.value,content=text); db.add(visitor); db.flush()
    history=[m.content for m in db.scalars(select(Message).where(Message.conversation_id==conversation.id).order_by(Message.created_at)).all()]
    lead=_lead(conversation,db); extraction=await extract(text,history)
    if extraction.email:lead.email=extraction.email
    if extraction.name:lead.name=extraction.name
    if extraction.company:lead.company=extraction.company
    updated=_merge(lead.bant_state,extraction,text); result=score_bant(lead.bant_state); lead.score=result.score; lead.qualification_status=result.status.value
    db.add(LeadScoreHistory(lead_id=lead.id,score=result.score,message_id=visitor.id))
    response_text=_assistant(lead.bant_state,result.status.value); bot=Message(conversation_id=conversation.id,role=MessageRole.BOT.value,content=response_text); db.add(bot)
    if result.status.value=="high_intent":
        for action_type,status,detail in [(RoutingActionType.SALES_ALERT.value,RoutingActionStatus.FAILED.value,"Provider not configured; recorded for retry."),(RoutingActionType.CALENDAR_BOOKING.value,RoutingActionStatus.PENDING.value,"Awaiting Calendly configuration.")]:
            key=f"{lead.id}:{action_type}:v1"
            if not db.scalar(select(RoutingAction).where(RoutingAction.idempotency_key==key)):db.add(RoutingAction(lead_id=lead.id,action_type=action_type,status=status,idempotency_key=key,result_detail=detail))
    db.commit(); db.refresh(lead); db.refresh(bot)
    return {"message":response_text,"lead":lead,"bant":lead.bant_state,"score":result,"updated":updated}
def conversation_snapshot(conversation:Conversation):
    lead=conversation.lead;b=lead.bant_state if lead else None
    return {"conversation_id":conversation.id,"status":conversation.status,"lead_score":lead.score if lead else 0,"qualification_status":lead.qualification_status if lead else "new","bant":{"budget":{"value":(str(b.budget_amount)+" "+(b.budget_currency or "") if b and b.budget_amount is not None else None),"confidence":b.budget_confidence if b else None},"authority":{"value":(b.authority_level if b and b.authority_level!="unknown" else None),"confidence":b.authority_confidence if b else None},"need":{"value":(b.need_summary if b and b.need_clarity!="unknown" else None),"confidence":b.need_confidence if b else None},"timeline":{"value":(b.timeline_urgency if b and b.timeline_urgency!="unknown" else None),"confidence":b.timeline_confidence if b else None}},"created_at":conversation.created_at,"updated_at":conversation.updated_at}
