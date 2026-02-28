import streamlit as st
import core.db as db
from core.auth import hash_password


def show():
    st.title("Admin: Users")

    users = db.get_all_users()

    # ─── User table ───────────────────────────────────────────────────────────
    st.subheader("All Users")
    for u in users:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
        col1.write(f"**{u['username']}**")
        col2.write("Admin" if u["is_admin"] else "User")
        col3.write("Active" if u["is_active"] else "Inactive")
        toggle_label = "Deactivate" if u["is_active"] else "Activate"
        if col4.button(toggle_label, key=f"toggle_{u['id']}"):
            db.set_user_active(u["id"], not u["is_active"])
            st.rerun()

    st.divider()

    # ─── Create user ──────────────────────────────────────────────────────────
    st.subheader("Create User")
    with st.form("create_user"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_is_admin = st.checkbox("Admin")
        if st.form_submit_button("Create"):
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif db.get_user_by_username(new_username):
                st.error("Username already exists.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                db.create_user(new_username, hash_password(new_password), is_admin=new_is_admin)
                st.success(f"User '{new_username}' created.")
                st.rerun()

    st.divider()

    # ─── Reset password ───────────────────────────────────────────────────────
    st.subheader("Reset Password")
    with st.form("reset_password"):
        usernames = [u["username"] for u in users]
        target = st.selectbox("User", usernames)
        new_pw = st.text_input("New password", type="password")
        if st.form_submit_button("Reset"):
            if not new_pw or len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                target_user = db.get_user_by_username(target)
                if target_user:
                    db.update_user_password(target_user["id"], hash_password(new_pw))
                    st.success(f"Password for '{target}' reset.")
