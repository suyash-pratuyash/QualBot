from fastapi.testclient import TestClient
from app.main import app
def test_health():
    with TestClient(app) as client:
        r=client.get("/api/v1/health"); assert r.status_code==200 and r.json()["status"]=="ok"
def test_login():
    with TestClient(app) as client:
        r=client.post("/api/v1/auth/login",json={"email":"admin@qualbot.local","password":"qualbot-demo"})
        assert r.status_code==200 and "access_token" in r.json()
