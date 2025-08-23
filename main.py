from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from config import get_settings
from auth import create_access_token, verify_password, hash_password, get_current_user, get_current_admin
from database import get_db
from sqlalchemy.orm import Session
from models import User, Order, Message, Feedback, Promocode, PromocodeUsage, OrderStatusHistory
from datetime import timedelta

settings = get_settings()
from database import engine
from models import Base as ModelBase
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not exist (for rapid bootstrap). In production use Alembic.
    try:
        ModelBase.metadata.create_all(bind=engine)
    except Exception as e:
        print("[startup] table creation failed", e)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(',')] if settings.cors_origins != '*' else ['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status":"ok"}

################ Admin Auth ################
from fastapi import Body

@app.post('/login')
def admin_login(username: str = Body(...), password: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username==username).first()
    if not user or user.role != 'admin' or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role})
    return {"success": True, "token": token}

############## Admin Orders ###############
@app.get('/api/orders')
def list_orders(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [serialize_order(o) for o in orders]

@app.get('/api/order/{order_id}')
def get_order_detail(order_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, 'Order not found')
    return serialize_order(o)

@app.put('/api/order/{order_id}')
def update_order(order_id: int, payload: dict, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, 'Order not found')
    allowed = {'status','notes'}
    changed=False
    for k,v in payload.items():
        if k in allowed:
            setattr(o,k,v); changed=True
    if changed:
        hist = OrderStatusHistory(order_id=order_id, status=o.status, changed_by=admin.id, notes=payload.get('notes'))
        db.add(hist)
        db.commit()
    return {"success": True}

@app.get('/api/feedbacks')
def admin_feedbacks(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    fbs = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(500).all()
    return [serialize_feedback(f) for f in fbs]

########## Admin Messages ##########
@app.get('/api/messages')
def admin_messages(user_id: Optional[int] = None, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    q = db.query(Message).order_by(Message.created_at.asc())
    if user_id:
        q = q.filter(Message.user_id==user_id, Message.order_id==None)
    else:
        q = q.filter(Message.order_id==None)
    msgs = q.limit(2000).all()
    return [serialize_message(m) for m in msgs]

@app.post('/api/send_file_to_user')
async def send_file_to_user(user_id: int = Form(...), file: UploadFile = File(...), admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    # Save file and record message (stub)
    import os, aiofiles
    os.makedirs(f'uploaded_files/support_{user_id}', exist_ok=True)
    path = f'uploaded_files/support_{user_id}/{file.filename}'
    async with aiofiles.open(path, 'wb') as out:
        content = await file.read(); await out.write(content)
    msg = Message(user_id=user_id, username='admin', direction='out', text=f'[file] {file.filename}', order_id=None, message_type='document')
    db.add(msg); db.commit(); db.refresh(msg)
    return {"success": True, "file": file.filename}

@app.get('/api/download_file/{file_id}')
def admin_download_file(file_id: str):
    # naive search in uploaded folders
    import glob, os
    matches = glob.glob(f'uploaded_files/**/{file_id}', recursive=True)
    if not matches:
        raise HTTPException(404, 'Not found')
    from fastapi.responses import FileResponse
    return FileResponse(matches[0], filename=file_id)

########## Messaging (admin -> user) ###########
@app.post('/api/send_message_to_user')
def send_message_to_user(user_id: int = Body(...), message: str = Body(...), order_id: Optional[int] = Body(None), db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    msg = Message(user_id=user_id, username='admin', direction='out', text=message, order_id=order_id)
    db.add(msg); db.commit()
    return {"success": True}

########## Broadcast ##########
@app.post('/api/broadcast')
async def broadcast(message: str = Form(...), file: Optional[UploadFile] = None, admin=Depends(get_current_admin)):
    # Placeholder: integrate with telegram bot to send broadcast
    return {"success": True, "sent": True, "file": file.filename if file else None}

########## Placeholder for sending files via telegram #########
@app.post('/api/send_order_files_to_admin')
def send_order_files_to_admin(order_id: int = Body(...), admin=Depends(get_current_admin)):
    # Implement telegram logic elsewhere
    return {"success": True, "message": "Stub: files dispatched"}

############ Client Auth #############
@app.post('/api/client/register')
def client_register(email: str = Body(...), username: str = Body(...), password: str = Body(...), db: Session = Depends(get_db)):
    if db.query(User).filter((User.email==email)|(User.username==username)).first():
        raise HTTPException(400, 'User exists')
    user = User(username=username, email=email, password_hash=hash_password(password), role='client')
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"token": token}

@app.post('/api/client/login')
def client_login(email: str = Body(...), password: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email==email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, 'Invalid credentials')
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"token": token}

@app.post('/api/client/auth-telegram')
def auth_telegram(telegram_id: int = Body(...), username: str = Body('User'), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id==telegram_id).first()
    if not user:
        user = User(username=username or f'user_{telegram_id}', telegram_id=telegram_id, password_hash=hash_password('telegram'))
        db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"token": token}

@app.post('/api/client/auth-google')
def auth_google(id_token: str = Body(...), db: Session = Depends(get_db)):
    # TODO: verify id_token with Google (omitted here) -> extract email, name
    email = f"google_{id_token[:8]}@example.com"
    username = f"g_{id_token[:6]}"
    user = db.query(User).filter(User.email==email).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password('google'), role='client')
        db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"token": token}

############ Client Orders ############
@app.post('/api/client/orders')
async def create_order(
    topic: str = Form(...),
    requirements: str = Form(...),
    order_type: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    volume: Optional[str] = Form(None),
    promocode: Optional[str] = Form(None),
    files: List[UploadFile] = [],
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    new_order = Order(
        id=generate_order_id(),
        user_id=user.id,
        first_name=user.username,
        username=user.username,
        topic=topic,
        requirements=requirements,
        order_type=order_type,
        subject=subject,
        deadline=deadline,
        volume=volume,
        files=[{"file_id": f.filename, "file_name": f.filename} for f in files] if files else [],
        status='pending'
    )
    db.add(new_order); db.commit();
    return {"order_id": new_order.id}

@app.get('/api/client/orders')
def client_orders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id==user.id).order_by(Order.created_at.desc()).all()
    return [serialize_order(o) for o in orders]

@app.get('/api/client/order/{order_id}')
def client_order_detail(order_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(404, 'Not found')
    return serialize_order(o)

@app.get('/api/client/order/{order_id}/messages')
def client_order_messages(order_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(404, 'Not found')
    msgs = db.query(Message).filter(Message.order_id==order_id).order_by(Message.created_at.asc()).all()
    return [serialize_message(m) for m in msgs]

@app.post('/api/client/order/{order_id}/upload')
async def upload_order_file(order_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(404, 'Not found')
    import os, aiofiles
    os.makedirs(f'uploaded_files/order_{order_id}', exist_ok=True)
    dest_path = f'uploaded_files/order_{order_id}/{file.filename}'
    async with aiofiles.open(dest_path, 'wb') as out:
        content = await file.read()
        await out.write(content)
    files = o.files or []
    files.append({"file_id": file.filename, "file_name": file.filename})
    o.files = files
    db.commit()
    return {"success": True}

@app.get('/api/client/order/{order_id}/files/{file_id}')
def download_order_file(order_id: int, file_id: str, user=Depends(get_current_user)):
    import os
    path = f'uploaded_files/order_{order_id}/{file_id}'
    if not os.path.isfile(path):
        raise HTTPException(404, 'File not found')
    from fastapi.responses import FileResponse
    return FileResponse(path, filename=file_id)

############ Support Chat #############
@app.get('/api/client/support/messages')
def support_messages(user=Depends(get_current_user), db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(Message.user_id==user.id, Message.order_id==None).order_by(Message.created_at.asc()).all()
    return [serialize_message(m) for m in msgs]

@app.post('/api/client/support/messages')
def send_support_message(text: str = Body(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    m = Message(user_id=user.id, username=user.username, direction='in', text=text, order_id=None)
    db.add(m); db.commit(); db.refresh(m)
    return serialize_message(m)

########### Feedbacks ###########
@app.get('/api/client/feedbacks')
def list_feedbacks(db: Session = Depends(get_db)):
    fbs = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(100).all()
    return [serialize_feedback(f) for f in fbs]

@app.post('/api/client/feedbacks')
def add_feedback(text: str = Body(...), stars: int = Body(5), user=Depends(get_current_user), db: Session = Depends(get_db)):
    fb = Feedback(user_id=user.id, username=user.username, text=text, stars=stars)
    db.add(fb); db.commit()
    return {"success": True}

@app.post('/api/client/feedbacks/public')
def add_feedback_public(text: str = Body(...), stars: int = Body(5), username: str = Body('Guest'), db: Session = Depends(get_db)):
    fb = Feedback(user_id=None, username=username, text=text, stars=stars)
    db.add(fb); db.commit()
    return {"success": True}

########### Promocode Validation ###########
@app.post('/api/client/promocode/validate')
def validate_promocode(code: str = Body(...), amount: int = Body(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    promo = db.get(Promocode, code)
    if not promo:
        return {"valid": False, "error": "Invalid code"}
    # Basic validation only here
    discount = 0
    if promo.discount_type == 'percent':
        discount = int(amount * (promo.discount_value or 0)/100)
    else:
        discount = int(promo.discount_value or 0)
    return {"valid": True, "discount": discount}

########### Prices (static config for now) ###########
PRICES = {
    "essay": {"label": "Есе", "base": 300, "per_page": 50},
    "coursework": {"label": "Курсова", "base": 1500, "per_page": 80},
    "thesis": {"label": "Диплом", "base": 5000, "per_page": 120}
}

@app.get('/api/client/prices')
def get_prices():
    return PRICES

########### FAQ (static) ###########
FAQ = [
    {"q": "Як створити замовлення?", "a": "Перейдіть до сторінки створення та заповніть форму."},
    {"q": "Як застосувати промокод?", "a": "Введіть код у відповідне поле при створенні замовлення."}
]

@app.get('/api/client/faq')
def get_faq():
    return FAQ

########### Profile & Stats ###########
@app.get('/api/client/profile/stats')
def profile_stats(user=Depends(get_current_user), db: Session = Depends(get_db)):
    def count(status):
        return db.query(Order).filter(Order.user_id==user.id, Order.status==status).count()
    total = db.query(Order).filter(Order.user_id==user.id).count()
    return {
        'total_orders': total,
        'pending': count('pending'),
        'in_progress': count('in_progress'),
        'completed': count('completed')
    }

@app.put('/api/client/profile')
def update_profile(username: str = Body(None), email: str = Body(None), phone: str = Body(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    changed=False
    if username and username != user.username:
        user.username = username; changed=True
    if email and email != user.email:
        user.email = email; changed=True
    # phone not stored - placeholder
    if changed:
        db.commit()
    return {"success": True}

########### Referrals ###########
@app.get('/api/client/referrals')
def referrals(user=Depends(get_current_user)):
    # Placeholder: implement real referral storage
    return []

########### Utils ###########
import random
def generate_order_id():
    return random.randint(10**8, 10**9-1)

def serialize_order(o: Order):
    return {
        'id': o.id,
        'user_id': o.user_id,
        'first_name': o.first_name,
        'username': o.username,
        'phone_number': o.phone_number,
        'type_label': o.type_label,
        'order_type': o.order_type,
        'topic': o.topic,
        'subject': o.subject,
        'deadline': o.deadline,
        'volume': o.volume,
        'requirements': o.requirements,
        'files': o.files or [],
        'price': o.price,
        'status': o.status,
        'created_at': o.created_at,
        'updated_at': o.updated_at,
        'confirmed_at': o.confirmed_at,
        'manager_id': o.manager_id,
        'notes': o.notes,
    }

def serialize_message(m: Message):
    return {
        'id': m.id,
        'user_id': m.user_id,
        'direction': m.direction,
        'text': m.text,
        'order_id': m.order_id,
        'created_at': m.created_at,
    }

def serialize_feedback(f: Feedback):
    return {
        'id': f.id,
        'username': f.username,
        'text': f.text,
        'stars': f.stars,
        'created_at': f.created_at,
    }
