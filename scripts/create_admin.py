#!/usr/bin/env python3
"""Bootstrap script: create the first admin user."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.auth import hash_password
import core.db as db


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 6:
        print("Error: password must be at least 6 characters.")
        sys.exit(1)

    existing = db.get_user_by_username(username)
    if existing:
        print(f"Error: user '{username}' already exists.")
        sys.exit(1)

    user_id = db.create_user(username, hash_password(password), is_admin=True)
    print(f"Admin user '{username}' created (id={user_id}).")


if __name__ == "__main__":
    main()
