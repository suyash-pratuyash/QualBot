"""BANT interpretation with optional Gemini and a safe local fallback."""
from __future__ import annotations
import json,re
from dataclasses import dataclass
from decimal import Decimal
import httpx
from app.core.config import get_settings
from app.domain.enums import BANTAuthorityLevel,BANTBudgetStatus,BANTNeedClarity,BANTTimelineUrgency
@dataclass
class Extraction:
    budget_status:str|None=None; budget_amount:Decimal|None=None; budget_currency:str|None=None; budget_confidence:float|None=None; budget_evidence:str|None=None
    authority_level:str|None=None; authority_confidence:float|None=None; authority_evidence:str|None=None
    need_clarity:str|None=None; need_summary:str|None=None; need_confidence:float|None=None; need_evidence:str|None=None
    timeline_urgency:str|None=None; timeline_confidence:float|None=None; timeline_evidence:str|None=None
    name:str|None=None; email:str|None=None; company:str|None=None
INJECTION_PATTERNS=re.compile(r"(ignore\s+(all|any|the)?\s*(previous|system|developer)|reveal\s+(your|the)\s+(system|hidden)\s+prompt|change\s+(the\s+)?score|pretend\s+you\s+are)",re.I)
def _heuristic(message:str)->Extraction:
    text=message.strip(); e=Extraction()
    if INJECTION_PATTERNS.search(text): return e
    money=re.search(r"(?:₹|rs\.?|inr\s*)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|lakh|lakhs|m|million)?",text,re.I) or re.search(r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s*(k|lakh|lakhs|m|million)\b",text,re.I)
    if money:
        raw=float(money.group(1).replace(",","")); suffix=(money.group(2) or "").lower(); multiplier=1000 if suffix=="k" else 100000 if suffix in {"lakh","lakhs"} else 1000000 if suffix in {"m","million"} else 1
        e.budget_amount=Decimal(str(raw*multiplier)).quantize(Decimal("0.01")); e.budget_currency="INR" if "₹" in text or re.search(r"\brs\.?|\binr\b",text,re.I) else "USD"; e.budget_status=BANTBudgetStatus.SPECIFIED.value; e.budget_confidence=.92; e.budget_evidence=text
    elif re.search(r"no budget available|cannot spend|can't spend|no funds",text,re.I): e.budget_status=BANTBudgetStatus.NONE_AVAILABLE.value; e.budget_confidence=.9; e.budget_evidence=text
    elif re.search(r"no budget|not sure (about|of) (the )?budget|budget is unclear",text,re.I): e.budget_status=BANTBudgetStatus.VAGUE.value; e.budget_confidence=.78; e.budget_evidence=text
    if re.search(r"i (am|['’]m) (the )?(owner|founder|ceo|cto)|i make the final decision|i decide|decision maker",text,re.I): e.authority_level=BANTAuthorityLevel.DECISION_MAKER.value; e.authority_confidence=.93; e.authority_evidence=text
    elif re.search(r"i('ll| will) evaluate|i('m| am) evaluating|reviewing options",text,re.I): e.authority_level=BANTAuthorityLevel.EVALUATOR.value; e.authority_confidence=.82; e.authority_evidence=text
    elif re.search(r"i influence|i recommend|my manager decides|not the final decision",text,re.I): e.authority_level=BANTAuthorityLevel.INFLUENCER.value; e.authority_confidence=.8; e.authority_evidence=text
    need=re.search(r"(?:need|looking for|want|require|problem is|goal is)\s+(.{8,180})",text,re.I)
    if need:
        e.need_summary=need.group(1).strip(" .!?"); e.need_clarity=BANTNeedClarity.SPECIFIC.value if len(e.need_summary.split())>=8 else BANTNeedClarity.CLEAR.value; e.need_confidence=.88; e.need_evidence=text
    elif re.search(r"chatbot|lead generation|automation|website|sales",text,re.I): e.need_summary=text; e.need_clarity=BANTNeedClarity.CLEAR.value; e.need_confidence=.72; e.need_evidence=text
    if re.search(r"today|this week|immediately|asap|right away",text,re.I): e.timeline_urgency=BANTTimelineUrgency.IMMEDIATE.value; e.timeline_confidence=.94; e.timeline_evidence=text
    elif re.search(r"this month|within (a )?month|next few weeks|2 weeks|three weeks",text,re.I): e.timeline_urgency=BANTTimelineUrgency.SHORT_TERM.value; e.timeline_confidence=.88; e.timeline_evidence=text
    elif re.search(r"next quarter|next year|6 months|six months|long term|long-term",text,re.I): e.timeline_urgency=BANTTimelineUrgency.LONG_TERM.value; e.timeline_confidence=.9; e.timeline_evidence=text
    email=re.search(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",text)
    if email:e.email=email.group(0)
    return e
async def extract(message:str,history:list[str])->Extraction:
    settings=get_settings()
    if not settings.gemini_key:return _heuristic(message)
    prompt=f"""Extract only evidence explicitly supported by this visitor message. Never infer missing BANT values. Return JSON with keys budget_status,budget_amount,budget_currency,budget_confidence,budget_evidence,authority_level,authority_confidence,authority_evidence,need_clarity,need_summary,need_confidence,need_evidence,timeline_urgency,timeline_confidence,timeline_evidence,name,email,company. Allowed budget_status: unknown,vague,specified,none_available. Allowed authority_level: unknown,influencer,evaluator,decision_maker. Allowed need_clarity: unknown,vague,clear,specific. Allowed timeline_urgency: unknown,long_term,short_term,immediate. Visitor message: {message} Recent history: {history[-6:]}"""
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json"}}
    try:
        async with httpx.AsyncClient(timeout=settings.gemini_timeout_seconds) as client:
            response=await client.post(url,params={"key":settings.gemini_key},json=body); response.raise_for_status()
            raw=response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return Extraction(**json.loads(raw))
    except Exception:return _heuristic(message)
