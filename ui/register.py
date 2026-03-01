import streamlit as st
import core.db as db
from core.auth import hash_password


def show():
    st.title("Register")

    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        password2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")

    if submitted:
        if not username or not password:
            st.error("Please fill in all fields.")
            return

        if password != password2:
            st.error("Passwords do not match.")
            return

        if len(password) < 8:
            st.error("Password must be at least 8 characters.")
            return

        if db.get_user_by_username(username) is not None:
            st.error("Username already taken.")
            return

        user_id = db.create_user(username, hash_password(password))
        user = db.get_user_by_username(username)
        user_session = {k: v for k, v in user.items() if k != "password_hash"}
        st.session_state["user"] = user_session
        st.rerun()
