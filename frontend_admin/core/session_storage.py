from streamlit_session_browser_storage import SessionStorage


def is_logged_in() -> bool:
    storage = SessionStorage()
    return bool(storage.getItem("access_token"))
