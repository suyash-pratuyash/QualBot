import pytest
from app.domain.models import Conversation, Lead, Message
from app.services.conversation import process_message
@pytest.mark.anyio
async def test_message_creates_lead_and_updates_score(db):
    c=Conversation(visitor_identifier="demo"); db.add(c); db.commit(); db.refresh(c)
    result=await process_message(db,c,"I am the founder. We need a website chatbot. Budget is ₹50,000 and we need it this month.")
    assert result["lead"].score>0
    assert result["lead"].bant_state.need_clarity in {"clear","specific"}
    assert db.query(Message).count()==2
