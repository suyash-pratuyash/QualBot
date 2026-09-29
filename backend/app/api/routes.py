"""QualBot REST and WebSocket endpoints."""
from __future__ import annotations
import math
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.api.schemas import (ActionResponse, AnalyticsResponse, BANTDimension, BANTResponse, ConversationCreate, ConversationCreateResponse, ConversationResponse, HealthResponse, LeadDetailResponse, LeadListItem, LeadListResponse, LeadStatusResponse, LeadStatusUpdate, LoginRequest, LoginResponse, MeResponse)
from app.domain.models import Conversation, Lead, Admin
from app.persistence.database import get_db
from app.services.auth import ensure_default_admin, issue_token, require_admin, verify_password
from app.services.conversation import conversation_snapshot, process_message
from app.services.analytics import overview
from app.integrations.providers import booking_url

router=APIRouter()
admin_router=APIRouter(dependencies=[Depends(require_admin)])

def not_found(code,message): raise HTTPException(404,detail={"code":code,"message":message,"details":None})

@router.get("/health",response_model=HealthResponse)
def health(): return {"status":"ok"}

@router.post("/auth/login",response_model=LoginResponse)
def login(payload:LoginRequest,db:Session=Depends(get_db)):
    admin=ensure_default_admin(db)
    if admin.email.lower()!=payload.email.lower() or not verify_password(payload.password,admin.hashed_password):
        raise HTTPException(401,detail={"code":"INVALID_CREDENTIALS","message":"Invalid credentials.","details":None})
    return {"access_token":issue_token(admin),"expires_in":3600}

@router.get("/auth/me",response_model=MeResponse)
def me(admin:Admin=Depends(require_admin)): return {"id":admin.id,"email":admin.email,"role":"admin"}

@router.post("/conversations",response_model=ConversationCreateResponse,status_code=201)
def create_conversation(payload:ConversationCreate,db:Session=Depends(get_db)):
    conversation=Conversation(visitor_identifier=payload.visitor_id,channel="web")
    db.add(conversation); db.commit(); db.refresh(conversation)
    return {"conversation_id":conversation.id,"status":conversation.status,"created_at":conversation.created_at}

@router.get("/conversations/{conversation_id}",response_model=ConversationResponse)
def get_conversation(conversation_id:str,db:Session=Depends(get_db)):
    conversation=db.query(Conversation).options(joinedload(Conversation.lead).joinedload(Lead.bant_state)).filter(Conversation.id==conversation_id).first()
    if not conversation: not_found("CONVERSATION_NOT_FOUND","Conversation not found.")
    return conversation_snapshot(conversation)

@router.get("/leads",response_model=LeadListResponse)
def list_leads(page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),status:str|None=None,min_score:int|None=Query(None,ge=0,le=100),max_score:int|None=Query(None,ge=0,le=100),db:Session=Depends(get_db),admin:Admin=Depends(require_admin)):
    if min_score is not None and max_score is not None and min_score>max_score: raise HTTPException(422,detail={"code":"VALIDATION_ERROR","message":"min_score cannot exceed max_score.","details":None})
    stmt=select(Lead).order_by(Lead.created_at.desc())
    if status: stmt=stmt.where(Lead.qualification_status==status)
    if min_score is not None: stmt=stmt.where(Lead.score>=min_score)
    if max_score is not None: stmt=stmt.where(Lead.score<=max_score)
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    leads=db.scalars(stmt.offset((page-1)*limit).limit(limit)).all()
    items=[{"lead_id":l.id,"conversation_id":l.conversation_id,"score":l.score,"qualification_status":l.qualification_status,"name":l.name,"company":l.company,"email":l.email,"created_at":l.created_at} for l in leads]
    return {"items":items,"pagination":{"page":page,"limit":limit,"total":total,"pages":math.ceil(total/limit) if total else 0}}

@router.get("/leads/{lead_id}",response_model=LeadDetailResponse)
def get_lead(lead_id:str,db:Session=Depends(get_db),admin:Admin=Depends(require_admin)):
    lead=db.query(Lead).options(joinedload(Lead.bant_state)).filter(Lead.id==lead_id).first()
    if not lead: not_found("LEAD_NOT_FOUND","Lead not found.")
    b=lead.bant_state
    routing={}
    for a in lead.routing_actions:
        if a.action_type=="sales_alert": routing["email_alert"]="sent" if a.status=="success" else a.status
        if a.action_type=="calendar_booking": routing["booking"]="available" if a.status=="success" else a.status
    return {"lead_id":lead.id,"conversation_id":lead.conversation_id,"score":lead.score,"qualification_status":lead.qualification_status,"name":lead.name,"company":lead.company,"email":lead.email,"created_at":lead.created_at,"updated_at":lead.updated_at,
      "bant":{"budget":{"value":str(b.budget_amount) + " " + (b.budget_currency or "") if b.budget_amount is not None else None,"confidence":b.budget_confidence},"authority":{"value":b.authority_level if b.authority_level!="unknown" else None,"confidence":b.authority_confidence},"need":{"value":b.need_summary if b.need_clarity!="unknown" else None,"confidence":b.need_confidence},"timeline":{"value":b.timeline_urgency if b.timeline_urgency!="unknown" else None,"confidence":b.timeline_confidence}},
      "routing":routing}

@router.patch("/leads/{lead_id}",response_model=LeadStatusResponse)
def update_lead(lead_id:str,payload:LeadStatusUpdate,db:Session=Depends(get_db),admin:Admin=Depends(require_admin)):
    lead=db.get(Lead,lead_id)
    if not lead: not_found("LEAD_NOT_FOUND","Lead not found.")
    lead.operational_status=payload.status; db.commit(); db.refresh(lead)
    return {"lead_id":lead.id,"status":lead.operational_status,"updated_at":lead.updated_at}

@router.get("/analytics/overview",response_model=AnalyticsResponse)
def analytics(db:Session=Depends(get_db),admin:Admin=Depends(require_admin)): return overview(db)

@router.post("/actions/{lead_id}/email-alert",response_model=ActionResponse)
def email_alert(lead_id:str,db:Session=Depends(get_db),admin:Admin=Depends(require_admin)):
    lead=db.get(Lead,lead_id)
    if not lead: not_found("LEAD_NOT_FOUND","Lead not found.")
    return {"action":"email_alert","status":"failed","lead_id":lead_id,"provider":"emailjs"}

@router.post("/actions/{lead_id}/booking",response_model=ActionResponse)
def booking(lead_id:str,db:Session=Depends(get_db),admin:Admin=Depends(require_admin)):
    lead=db.get(Lead,lead_id)
    if not lead: not_found("LEAD_NOT_FOUND","Lead not found.")
    url=booking_url()
    if not url: return {"action":"booking","status":"unavailable","lead_id":lead_id,"provider":"calendly","url":None}
    return {"action":"booking","status":"available","lead_id":lead_id,"provider":"calendly","url":url}

async def websocket_conversation(websocket:WebSocket,conversation_id:str):
    await websocket.accept()
    from app.persistence.database import _get_session_factory
    db=_get_session_factory()()
    try:
        conversation=db.query(Conversation).options(joinedload(Conversation.lead).joinedload(Lead.bant_state)).filter(Conversation.id==conversation_id).first()
        if not conversation:
            await websocket.send_json({"type":"error","code":"CONVERSATION_NOT_FOUND","message":"Conversation not found."}); await websocket.close(code=1008); return
        while True:
            event=await websocket.receive_json()
            if event.get("type")!="user_message" or not isinstance(event.get("message"),str) or not 1<=len(event["message"])<=2000:
                await websocket.send_json({"type":"error","code":"INVALID_WEBSOCKET_MESSAGE","message":"Invalid message."}); continue
            result=await process_message(db,conversation,event["message"])
            await websocket.send_json({"type":"assistant_message","message":result["message"]})
            await websocket.send_json({"type":"bant_update","updated":result["updated"],"completion":result["score"].completeness})
            await websocket.send_json({"type":"score_update","score":result["score"].score})
            await websocket.send_json({"type":"qualification_update","status":result["score"].status.value})
            if result["score"].status.value=="high_intent":
                url=booking_url()
                if url: await websocket.send_json({"type":"booking_available","provider":"calendly","url":url})
    except WebSocketDisconnect: pass
    finally: db.close()
