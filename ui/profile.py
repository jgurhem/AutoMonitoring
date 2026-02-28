import streamlit as st
import core.db as db
from core.auth import hash_password, verify_password


def show(user: dict):
    st.title("Profile")
    user_id = user["id"]

    # ─── Change password ──────────────────────────────────────────────────────
    st.subheader("Change Password")
    with st.form("change_password"):
        current_pw = st.text_input("Current password", type="password")
        new_pw = st.text_input("New password", type="password")
        new_pw2 = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Update password"):
            full_user = db.get_user_by_username(user["username"])
            if not verify_password(current_pw, full_user["password_hash"]):
                st.error("Current password is incorrect.")
            elif new_pw != new_pw2:
                st.error("New passwords do not match.")
            elif len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                db.update_user_password(user_id, hash_password(new_pw))
                st.success("Password updated.")

    st.divider()

    # ─── Processing defaults ──────────────────────────────────────────────────
    st.subheader("Processing Defaults")
    with st.form("prefs_form"):
        novelty_threshold = st.slider(
            "Novelty threshold", 0.0, 1.0,
            float(user.get("pref_novelty_threshold") or 0.6), 0.05,
        )
        digest_days = st.number_input(
            "Digest days", 1, 30,
            int(user.get("pref_digest_days") or 7),
        )
        digest_novelty_threshold = st.slider(
            "Digest novelty threshold (optional)", 0.0, 1.0,
            float(user.get("pref_digest_novelty_threshold") or 0.5), 0.05,
        )
        if st.form_submit_button("Save defaults"):
            db.update_user_prefs(
                user_id,
                pref_novelty_threshold=novelty_threshold,
                pref_digest_days=int(digest_days),
                pref_digest_novelty_threshold=digest_novelty_threshold,
            )
            # Refresh session state
            updated = db.get_user_by_username(user["username"])
            st.session_state["user"] = {k: v for k, v in updated.items() if k != "password_hash"}
            st.success("Defaults saved.")

    st.divider()

    # ─── RSS subscriptions ────────────────────────────────────────────────────
    st.subheader("RSS Feed Subscriptions")

    current_feeds = db.get_user_rss_feeds(user_id)
    if current_feeds:
        for feed in current_feeds:
            col1, col2 = st.columns([5, 1])
            col1.write(f"**{feed['name'] or feed['url']}**  \n{feed['url']}")
            if col2.button("Remove", key=f"unsub_rss_{feed['feed_id']}"):
                db.unsubscribe_user_from_feed(user_id, feed["feed_id"])
                st.rerun()
    else:
        st.caption("No RSS feeds subscribed.")

    st.write("**Add a feed:**")
    with st.form("add_rss_feed"):
        new_feed_url = st.text_input("Feed URL")
        new_feed_name = st.text_input("Display name (optional)")
        # Also show existing catalog feeds not yet subscribed
        all_feeds = db.get_all_rss_feeds()
        subscribed_ids = {f["feed_id"] for f in current_feeds}
        catalog_feeds = [f for f in all_feeds if f["id"] not in subscribed_ids]
        catalog_options = ["(enter URL above)"] + [f"{f['name'] or f['url']}" for f in catalog_feeds]
        catalog_sel = st.selectbox("Or pick from catalog", catalog_options)

        if st.form_submit_button("Subscribe"):
            if catalog_sel != "(enter URL above)" and catalog_feeds:
                idx = catalog_options.index(catalog_sel) - 1
                feed_id = catalog_feeds[idx]["id"]
                db.subscribe_user_to_feed(user_id, feed_id)
                st.success("Subscribed.")
                st.rerun()
            elif new_feed_url:
                feed_id = db.get_or_create_rss_feed(new_feed_url, new_feed_name or None)
                db.subscribe_user_to_feed(user_id, feed_id)
                st.success("Subscribed.")
                st.rerun()
            else:
                st.error("Enter a URL or select a feed from the catalog.")

    st.divider()

    # ─── ArXiv subscriptions ──────────────────────────────────────────────────
    st.subheader("ArXiv Search Subscriptions")

    current_searches = db.get_user_arxiv_searches(user_id)
    if current_searches:
        for s in current_searches:
            col1, col2 = st.columns([5, 1])
            col1.write(f"`{s['query']}`  (max {s['max_results']} results)")
            if col2.button("Remove", key=f"unsub_arxiv_{s['search_id']}"):
                db.unsubscribe_user_from_search(user_id, s["search_id"])
                st.rerun()
    else:
        st.caption("No arXiv searches subscribed.")

    st.write("**Add a search:**")
    with st.form("add_arxiv_search"):
        new_query = st.text_input("arXiv query")
        new_max = st.number_input("Max results", 1, 200, 10)
        all_searches = db.get_all_arxiv_searches()
        subscribed_search_ids = {s["search_id"] for s in current_searches}
        catalog_searches = [s for s in all_searches if s["id"] not in subscribed_search_ids]
        search_options = ["(enter query above)"] + [s["query"][:80] for s in catalog_searches]
        search_sel = st.selectbox("Or pick from catalog", search_options)

        if st.form_submit_button("Subscribe"):
            if search_sel != "(enter query above)" and catalog_searches:
                idx = search_options.index(search_sel) - 1
                search_id = catalog_searches[idx]["id"]
                db.subscribe_user_to_search(user_id, search_id)
                st.success("Subscribed.")
                st.rerun()
            elif new_query:
                search_id = db.get_or_create_arxiv_search(new_query, int(new_max))
                db.subscribe_user_to_search(user_id, search_id)
                st.success("Subscribed.")
                st.rerun()
            else:
                st.error("Enter a query or select from the catalog.")
