"""Minimal Flask version of the backend focused on admin panel endpoints.

Implements only the endpoints currently used by the React admin frontend:
  POST   /login
  GET    /api/orders (optional ?user_id=)
  GET    /api/order/<order_id>
  PUT    /api/order/<order_id>
  GET    /api/messages (optional ?user_id=)
  POST   /api/send_message_to_user
  POST   /api/send_file_to_user (multipart)
  POST   /api/send_order_files_to_admin (stub)
  GET    /api/feedbacks
  POST   /api/broadcast (stub)
  GET    /health

Client endpoints from the FastAPI version can be added later if needed.

Run locally:
  python flask_app.py

For production (Procfile updated):
  gunicorn flask_app:app --bind 0.0.0.0:$PORT
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from jose import jwt, JWTError
from passlib.context import CryptContext

from config import get_settings
from database import SessionLocal
from models import User, Order, Message, Feedback, OrderStatusHistory

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
# Configure CORS using settings.cors_origins. If wildcard '*' is used we must not enable
# supports_credentials because browsers won't accept '*' together with Access-Control-Allow-Credentials: true.
if hasattr(settings, 'cors_origins') and settings.cors_origins and settings.cors_origins.strip() != '*':
    _origins = [o.strip() for o in settings.cors_origins.split(',') if o.strip()]
    _supports_credentials = True
else:
    _origins = '*'
    _supports_credentials = False

CORS(app, resources={r"/*": {"origins": _origins}}, supports_credentials=_supports_credentials)

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), '..', 'uploaded_files')
os.makedirs(UPLOAD_ROOT, exist_ok=True)


# -------------------- Helpers --------------------
def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=minutes or settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def token_required(admin: bool = False):
    """Decorator enforcing JWT auth. If admin=True also checks role."""
    def wrapper(fn):
        from functools import wraps

        @wraps(fn)
        def inner(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({"error": "Missing token"}), 401
            token = auth_header.split(' ', 1)[1].strip()
            try:
                payload = decode_token(token)
            except JWTError:
                return jsonify({"error": "Invalid token"}), 401
            user_id = payload.get('user_id')
            if not user_id:
                return jsonify({"error": "Invalid payload"}), 401
            db = SessionLocal()
            try:
                user = db.get(User, user_id)
                if not user:
                    return jsonify({"error": "User not found"}), 401
                if admin and user.role != 'admin':
                    return jsonify({"error": "Admin only"}), 403
                # attach to request context
                request.current_user = user  # type: ignore[attr-defined]
                request.db = db             # type: ignore[attr-defined]
                return fn(*args, **kwargs)
            finally:
                # routes that commit must do so before returning; we close afterwards
                db.close()
        return inner
    return wrapper


def generate_order_id() -> int:
    return random.randint(10 ** 8, 10 ** 9 - 1)


def dt(v):
    return v.isoformat() if isinstance(v, datetime) else v


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
        'created_at': dt(o.created_at),
        'updated_at': dt(o.updated_at),
        'confirmed_at': dt(o.confirmed_at),
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
        'created_at': dt(m.created_at),
    }


def serialize_feedback(f: Feedback):
    return {
        'id': f.id,
        'user_id': getattr(f, 'user_id', None),
        'username': f.username,
        'text': f.text,
        'stars': f.stars,
        'created_at': dt(f.created_at),
    }


# -------------------- Routes --------------------
@app.get('/health')
def health():
    return jsonify({"status": "ok"})


@app.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({"success": False, "error": "Missing credentials"}), 400
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or user.role != 'admin' or not verify_password(password, user.password_hash):
            return jsonify({"success": False, "error": "Invalid credentials"}), 401
        token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role})
        return jsonify({"success": True, "token": token})
    finally:
        db.close()


@app.get('/api/orders')
@token_required(admin=True)
def list_orders():
    db = SessionLocal()
    try:
        q = db.query(Order).order_by(Order.created_at.desc())
        user_id = request.args.get('user_id')
        if user_id:
            try:
                q = q.filter(Order.user_id == int(user_id))
            except ValueError:
                pass
        orders = q.all()
        return jsonify([serialize_order(o) for o in orders])
    finally:
        db.close()


@app.get('/api/order/<int:order_id>')
@token_required(admin=True)
def order_detail(order_id: int):
    db = SessionLocal()
    try:
        o = db.get(Order, order_id)
        if not o:
            return jsonify({"error": "Order not found"}), 404
        return jsonify(serialize_order(o))
    finally:
        db.close()


@app.put('/api/order/<int:order_id>')
@token_required(admin=True)
def update_order(order_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        o = db.get(Order, order_id)
        if not o:
            return jsonify({"error": "Order not found"}), 404
        changed = False
        for field in ('status', 'notes'):
            if field in data:
                setattr(o, field, data[field])
                changed = True
        if changed:
            hist = OrderStatusHistory(order_id=order_id, status=o.status, changed_by=getattr(request, 'current_user').id, notes=data.get('notes'))  # type: ignore
            db.add(hist)
            db.commit()
        return jsonify({"success": True})
    finally:
        db.close()


@app.get('/api/messages')
@token_required(admin=True)
def list_messages():
    user_id = request.args.get('user_id')
    db = SessionLocal()
    try:
        q = db.query(Message).order_by(Message.created_at.asc()).filter(Message.order_id == None)  # noqa: E711
        if user_id:
            try:
                q = q.filter(Message.user_id == int(user_id))
            except ValueError:
                pass
        msgs = q.limit(2000).all()
        return jsonify([serialize_message(m) for m in msgs])
    finally:
        db.close()


@app.post('/api/send_message_to_user')
@token_required(admin=True)
def send_message_to_user():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    text = (data.get('message') or '').strip()
    order_id = data.get('order_id')
    if not user_id or not text:
        return jsonify({"success": False, "error": "Missing user_id or message"}), 400
    db = SessionLocal()
    try:
        msg = Message(user_id=user_id, username='admin', direction='out', text=text, order_id=order_id)
        db.add(msg)
        db.commit()
        return jsonify({"success": True})
    finally:
        db.close()


@app.post('/api/send_file_to_user')
@token_required(admin=True)
def send_file_to_user():
    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400
    try:
        user_id_int = int(user_id)
    except ValueError:
        return jsonify({"success": False, "error": "invalid user_id"}), 400
    file = request.files.get('file')
    if not file:
        return jsonify({"success": False, "error": "file missing"}), 400
    user_dir = os.path.join(UPLOAD_ROOT, f'support_{user_id_int}')
    os.makedirs(user_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    dest_path = os.path.join(user_dir, filename)
    file.save(dest_path)
    db = SessionLocal()
    try:
        msg = Message(user_id=user_id_int, username='admin', direction='out', text=f'[file] {filename}', order_id=None, message_type='document')
        db.add(msg)
        db.commit()
        return jsonify({"success": True, "file": filename})
    finally:
        db.close()


@app.post('/api/send_order_files_to_admin')
@token_required(admin=True)
def send_order_files_to_admin():
    # Stub for compatibility with frontend button
    return jsonify({"success": True, "message": "Stub: files dispatched"})


@app.get('/api/feedbacks')
@token_required(admin=True)
def feedbacks():
    db = SessionLocal()
    try:
        fbs = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(500).all()
        return jsonify([serialize_feedback(f) for f in fbs])
    finally:
        db.close()


@app.post('/api/broadcast')
@token_required(admin=True)
def broadcast():
    # Placeholder: integrate with Telegram bot later
    message = request.form.get('message') or request.values.get('message') or ''
    return jsonify({"success": True, "sent": True, "echo": message})


# -------------- File download (admin uploaded) --------------
@app.get('/api/download_file/<path:filename>')
@token_required(admin=True)
def download_file(filename: str):
    # naive search inside UPLOAD_ROOT
    for root, _dirs, files in os.walk(UPLOAD_ROOT):
        if filename in files:
            return send_file(os.path.join(root, filename), as_attachment=True, download_name=filename)
    return jsonify({"error": "Not found"}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=settings.debug)
