"""JWT authentication helpers and demo-admin bootstrap."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import bcrypt,jwt
from fastapi import Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.domain.models import Admin
from app.persistence.database import get_db
bearer=HTTPBearer(auto_error=False)
def hash_password(password:str)->str:return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
def verify_password(password:str,hashed:str)->bool:
    try:return bcrypt.checkpw(password.encode(),hashed.encode())
    except (ValueError,TypeError):return False
def ensure_default_admin(db:Session)->Admin:
    s=get_settings(); admin=db.query(Admin).filter(Admin.email==s.admin_email).first()
    if admin:return admin
    admin=Admin(email=s.admin_email,hashed_password=hash_password(s.admin_password),display_name="QualBot Admin",is_active=True);db.add(admin);db.commit();db.refresh(admin);return admin
def issue_token(admin:Admin)->str:
    s=get_settings();now=datetime.now(timezone.utc)
    return jwt.encode({"sub":admin.id,"email":admin.email,"role":"admin","iat":now,"exp":now+timedelta(seconds=s.jwt_expiry_seconds)},s.jwt_secret,algorithm="HS256")
def require_admin(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db))->Admin:
    if not credentials:raise HTTPException(401,detail={"code":"AUTHENTICATION_REQUIRED","message":"Authentication required.","details":None})
    try:payload=jwt.decode(credentials.credentials,get_settings().jwt_secret,algorithms=["HS256"])
    except jwt.PyJWTError as exc:raise HTTPException(401,detail={"code":"INVALID_TOKEN","message":"Invalid or expired token.","details":None}) from exc
    admin=db.get(Admin,payload.get("sub"))
    if not admin or not admin.is_active:raise HTTPException(403,detail={"code":"FORBIDDEN","message":"Administrator access required.","details":None})
    return admin
