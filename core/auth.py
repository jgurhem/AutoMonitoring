from passlib.hash import argon2
import streamlit as st


def hash_password(password: str) -> str:
    return argon2.hash(password)


def verify_password(password: str, hash: str) -> bool:
    return argon2.verify(password, hash)


def require_login():
    """Call at top of every protected page. Stops execution if not authenticated."""
    if "user" not in st.session_state:
        st.error("You must be logged in to access this page.")
        st.stop()


def require_admin():
    """Stops execution if current user is not admin."""
    require_login()
    if not st.session_state["user"].get("is_admin"):
        st.error("Admin access required.")
        st.stop()


def current_user() -> dict | None:
    return st.session_state.get("user")
