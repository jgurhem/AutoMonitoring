from passlib.hash import argon2
import streamlit as st


def hash_password(password: str) -> str:
    return argon2.hash(password)


def verify_password(password: str, hash: str) -> bool:
    return argon2.verify(password, hash)


def current_user() -> dict | None:
    return st.session_state.get("user")
