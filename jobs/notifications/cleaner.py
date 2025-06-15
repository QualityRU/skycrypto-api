from utils.db_sessions import session_scope


def clean():
    with session_scope() as session:
        session.execute("DELETE FROM notification WHERE created_at < NOW() - INTERVAL '1 hour'")
