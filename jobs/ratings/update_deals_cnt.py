from utils.db_sessions import session_scope


def _get_users(session):
    q = """
        SELECT id
        FROM "user" 
        WHERE last_action > NOW() - INTERVAL '3 hours' AND NOT is_temporary AND
            nickname NOT LIKE 'fd%' AND nickname NOT LIKE 'fs%'
    """
    return [dict(item) for item in session.execute(q).fetchall()]


def _get_deals_count_revenue(user_id, session):
    q = """
        SELECT COUNT(*), COALESCE(SUM(amount_currency), 0)
        FROM deal
        WHERE (buyer_id = :uid OR seller_id = :uid) AND state = 'closed'
    """
    return session.execute(q, {'uid': user_id}).fetchone()


def update_deals_cnt():
    with session_scope() as session:
        users = _get_users(session)
    for user in users:
        with session_scope() as session:
            deals, revenue = _get_deals_count_revenue(user['id'], session)
            q = """
                UPDATE "user" u
                SET deals_cnt = :deals, deals_revenue = :revenue
                WHERE id = :uid
            """
            session.execute(q, {'uid': user['id'], 'deals': deals, 'revenue': revenue})
