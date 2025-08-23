"""Utility script to create or update an admin user for the Flask backend.

Usage (PowerShell):
  set USERNAME=admin; set PASSWORD=admin123; python create_admin.py

Or provide inline:
  python create_admin.py --username admin --password admin123
"""
from __future__ import annotations

import argparse
import os
from passlib.context import CryptContext

from database import SessionLocal
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def ensure_admin(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.password_hash = hash_password(password)
            user.role = 'admin'
            action = 'updated'
        else:
            user = User(username=username, password_hash=hash_password(password), role='admin')
            db.add(user)
            action = 'created'
        db.commit()
        print(f"Admin user '{username}' {action} successfully.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default=os.environ.get('USERNAME', 'admin'))
    parser.add_argument('--password', default=os.environ.get('PASSWORD', 'admin123'))
    args = parser.parse_args()
    ensure_admin(args.username, args.password)


if __name__ == '__main__':
    main()
