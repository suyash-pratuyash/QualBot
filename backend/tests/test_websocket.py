from fastapi.testclient import TestClient
from app.main import app

def test_websocket_qualification_flow():
    with TestClient(app) as client:
        response=client.post('/api/v1/conversations',json={'visitor_id':'ws-test'})
        conversation_id=response.json()['conversation_id']
        with client.websocket_connect('/ws/v1/conversations/'+conversation_id) as ws:
            ws.send_json({'type':'user_message','message':'I am the founder. We need a website chatbot for lead generation. Budget is ₹50,000 and we need it this week.'})
            events=[ws.receive_json() for _ in range(4)]
            assert any(e['type']=='assistant_message' for e in events)
            assert any(e['type']=='score_update' and e['score']>=70 for e in events)
            assert any(e['type']=='qualification_update' and e['status']=='high_intent' for e in events)
