"""Pydantic request/response models for QualBot APIs."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl
class APIModel(BaseModel):
    model_config=ConfigDict(from_attributes=True)
class ErrorBody(APIModel):
    code:str; message:str; details:object|None=None
class ErrorResponse(APIModel): error:ErrorBody
class LoginRequest(APIModel): email:EmailStr; password:str=Field(min_length=1,max_length=200)
class LoginResponse(APIModel): access_token:str; token_type:str="bearer"; expires_in:int
class MeResponse(APIModel): id:str; email:EmailStr; role:str="admin"
class ConversationCreate(APIModel): visitor_id:str=Field(min_length=1,max_length=100); page_url:HttpUrl|None=None
class ConversationCreateResponse(APIModel): conversation_id:str; status:str; created_at:datetime
class BANTDimension(APIModel): value:object|None=None; confidence:float|None=Field(default=None,ge=0,le=1)
class BANTResponse(APIModel): budget:BANTDimension; authority:BANTDimension; need:BANTDimension; timeline:BANTDimension
class ConversationResponse(APIModel):
    conversation_id:str; status:str; lead_score:int; qualification_status:str; bant:BANTResponse; created_at:datetime; updated_at:datetime
class MessageRequest(APIModel): type:str; message:str=Field(min_length=1,max_length=2000)
class LeadListItem(APIModel):
    lead_id:str; conversation_id:str; score:int; qualification_status:str; name:str|None=None; company:str|None=None; email:str|None=None; created_at:datetime
class Pagination(APIModel): page:int; limit:int; total:int; pages:int
class LeadListResponse(APIModel): items:list[LeadListItem]; pagination:Pagination
class LeadDetailResponse(LeadListItem): bant:BANTResponse; routing:dict[str,str|None]; updated_at:datetime
class LeadStatusUpdate(APIModel): status:str=Field(pattern="^(new|contacted|converted|closed)$")
class LeadStatusResponse(APIModel): lead_id:str; status:str; updated_at:datetime
class AnalyticsResponse(APIModel):
    total_conversations:int; total_leads:int; qualified_leads:int; high_intent_leads:int; average_lead_score:float; conversion_rate:float
class ActionResponse(APIModel):
    action:str; status:str; lead_id:str; provider:str|None=None; url:str|None=None
class HealthResponse(APIModel): status:str
