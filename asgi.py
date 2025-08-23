from main import app
import socketio
from config import get_settings
from jose import jwt
from models import Message
from database import SessionLocal
from main import serialize_message, serialize_order

settings = get_settings()

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
def connect(sid, environ, auth):
    token = None
    if isinstance(auth, dict):
        token = auth.get('token')
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        return False
    sio.save_session(sid, {'user_id': payload.get('user_id'), 'username': payload.get('username')})

@sio.event
def disconnect(sid):
    pass

@sio.event
async def join(sid, data):
    sess = sio.get_session(sid)
    if not sess: return
    await sio.enter_room(sid, f"user_{sess['user_id']}")

@sio.event
async def join_order_room(sid, data):
    sess = sio.get_session(sid)
    if not sess: return
    order_id = data.get('order_id') if isinstance(data, dict) else None
    if not order_id: return
    await sio.enter_room(sid, f'order_{order_id}')

@sio.event
async def leave_order_room(sid, data):
    order_id = data.get('order_id') if isinstance(data, dict) else None
    if not order_id: return
    await sio.leave_room(sid, f'order_{order_id}')

@sio.event
async def send_message(sid, data):
    sess = sio.get_session(sid)
    if not sess: return
    order_id = data.get('order_id')
    text = data.get('text','').strip()
    client_msg_id = data.get('client_message_id')
    if not order_id or not text: return
    db = SessionLocal()
    try:
        msg = Message(user_id=sess['user_id'], username=sess['username'], direction='in', text=text, order_id=order_id)
        db.add(msg); db.commit(); db.refresh(msg)
        payload = serialize_message(msg)
        if client_msg_id: payload['client_message_id'] = client_msg_id
        await sio.emit('new_message', payload, room=f'order_{order_id}')
    finally:
        db.close()

@sio.event
async def send_user_message(sid, data):
    sess = sio.get_session(sid)
    if not sess: return
    text = data.get('text','').strip()
    client_msg_id = data.get('client_message_id')
    if not text: return
    db = SessionLocal()
    try:
        msg = Message(user_id=sess['user_id'], username=sess['username'], direction='in', text=text, order_id=None)
        db.add(msg); db.commit(); db.refresh(msg)
        payload = serialize_message(msg)
        if client_msg_id: payload['client_message_id'] = client_msg_id
        await sio.emit('new_support_message', payload, room=f"user_{sess['user_id']}")
    finally:
        db.close()

application = socketio.ASGIApp(sio, other_asgi_app=app)
