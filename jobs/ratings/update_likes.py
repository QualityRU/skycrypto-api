import math
import time
from decimal import Decimal

from utils.db_sessions import session_scope
from utils.logger import logger


def _get_users(session):
    last_likes_users = "SELECT from_user_id, to_user_id FROM userrate WHERE created_at > NOW() - interval '1 hour'"
    users = set()
    for item in session.execute(last_likes_users).fetchall():
        users.add(item['from_user_id'])
        users.add(item['to_user_id'])

    return tuple(users)


def _update_likes_dislikes(item, session):
    q = """
       UPDATE "user"
       SET total_likes = :likes, total_dislikes = :dislikes
       WHERE id = :uid
    """
    session.execute(q, item)


def _get_total_likes_dislikes(users, session) -> list:
    final_data = []

    if not users:
        return []

    old_likes = session.execute(
        """
            SELECT id, likes, dislikes
            FROM "user"
            WHERE id in :uid
        """, {'uid': users}
    ).fetchall()

    for user_id, likes, dislikes in old_likes:
        final_data.append({'uid': user_id, 'likes': likes, 'dislikes': dislikes})

    q = """
       SELECT to_user_id, action, COALESCE(COUNT(*), 0)
       FROM userrate
       WHERE to_user_id in :uid
       GROUP BY to_user_id, action
    """
    new_likes = session.execute(q, {'uid': users}).fetchall()
    for user_id, action, cnt in new_likes:
        obj = next(filter(lambda x: x['uid'] == user_id, final_data))
        obj[f'{action}s'] += cnt

    return final_data


def update_likes():
    with session_scope() as session:
        users = _get_users(session)
        logger.info(f'users to update likes {len(users)}')
        users_likes = _get_total_likes_dislikes(users, session)  # [{123: {'likes': 123, 'dislikes': 1}},]
    for item in users_likes:
        with session_scope() as session:
            _update_likes_dislikes(item, session)
        time.sleep(0.5)
    logger.info(f'Ratings calculated')
