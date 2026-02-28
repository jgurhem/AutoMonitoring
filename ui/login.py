import streamlit as st
import core.db as db
from core.auth import verify_password


def show():
    st.title("Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if not username or not password:
            st.error("Please enter username and password.")
            return

        user = db.get_user_by_username(username)
        if user is None or not user["is_active"]:
            st.error("Invalid username or password.")
            return

        if not verify_password(password, user["password_hash"]):
            st.error("Invalid username or password.")
            return

        # Remove password_hash from session state for security
        user_session = {k: v for k, v in user.items() if k != "password_hash"}
        st.session_state["user"] = user_session
        st.rerun()
