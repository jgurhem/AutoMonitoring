import argparse
import io
import logging

from streamlit_js_eval import streamlit_js_eval

import streamlit as st

import core.db as db
from core.auth import current_user

st.set_page_config(page_title="Monitoring", layout="wide", page_icon="📡")

# ─── Auth gate ───────────────────────────────────────────────────────────────

if "user" not in st.session_state:
    _auth_tab = st.session_state.get("auth_tab", "Login")
    col_l, col_r, _ = st.columns([1, 1, 4])
    if col_l.button("Login", type="primary" if _auth_tab == "Login" else "secondary"):
        st.session_state["auth_tab"] = "Login"
        st.rerun()
    if col_r.button("Register", type="primary" if _auth_tab == "Register" else "secondary"):
        st.session_state["auth_tab"] = "Register"
        st.rerun()
    if _auth_tab == "Register":
        from ui.register import show as show_register
        show_register()
    else:
        from ui.login import show as show_login
        show_login()
    st.stop()

user = current_user()

# ─── Shared helpers ──────────────────────────────────────────────────────────

_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_parser.add_argument("--model", default="mixtral")
_args, _ = _arg_parser.parse_known_args()
ollama_model = _args.model

_screen_width = streamlit_js_eval(js_expressions="window.innerWidth", key="screen_width")
wrap_width = max(80, int((_screen_width - 304) / 7.5)) if _screen_width else 120


def capture_run(fn):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        fn()
    except Exception as e:
        buf.write(f"\nERROR: {e}\n")
    finally:
        root.removeHandler(handler)
    return buf.getvalue()


# ─── Sidebar extras ──────────────────────────────────────────────────────────

with st.sidebar:
    st.caption(
        f"Logged in as **{user['username']}**"
        + (" (admin)" if user.get("is_admin") else "")
    )
    if st.button("Logout"):
        del st.session_state["user"]
        st.rerun()

# ─── Page imports ─────────────────────────────────────────────────────────────

from ui.browse import show as _browse
from ui.semantic_search import show as _semantic_search
from ui.novelty import show as _novelty
from ui.cluster import show as _cluster
from ui.digest import show as _digest
from ui.favorites import show as _favorites
from ui.profile import show as _profile
from ui.stats import show as _stats
from ui.admin_users import show as _admin_users
from ui.admin_dedup import show as _admin_dedup

# ─── Navigation ───────────────────────────────────────────────────────────────

main_pages = [
    st.Page(lambda: _browse(user),                                        title="Browse",          icon=":material/article:",         url_path="browse",  default=True),
    st.Page(lambda: _semantic_search(user),                               title="Semantic Search", icon=":material/search:",          url_path="search"),
    st.Page(lambda: _novelty(user, capture_run, wrap_width),              title="Novelty",         icon=":material/auto_awesome:",    url_path="novelty"),
    st.Page(lambda: _cluster(user, capture_run, wrap_width),              title="Cluster",         icon=":material/hub:",             url_path="cluster"),
    st.Page(lambda: _digest(user, capture_run, wrap_width, ollama_model), title="Digest",          icon=":material/summarize:",       url_path="digest"),
    st.Page(lambda: _favorites(user),                                     title="Favorites",       icon=":material/star:",            url_path="favorites"),
    st.Page(lambda: _profile(user),                                       title="Profile",         icon=":material/person:",          url_path="profile"),
]

if user.get("is_admin"):
    admin_pages = [
        st.Page(lambda: _stats(),        title="Stats",  icon=":material/bar_chart:",       url_path="admin-stats"),
        st.Page(lambda: _admin_users(),  title="Users",  icon=":material/manage_accounts:", url_path="admin-users"),
        st.Page(lambda: _admin_dedup(),  title="Dedup",  icon=":material/content_copy:",    url_path="admin-dedup"),
    ]
    pg = st.navigation({"": main_pages, "Admin": admin_pages})
else:
    pg = st.navigation(main_pages)

pg.run()
