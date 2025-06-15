import math
import time
from decimal import Decimal

from utils.db_sessions import session_scope
from utils.logger import logger


def _get_rating_points(user):
    dislikes_weight = -2
    likes_weight = 1
    deals_weight = Decimal('0.4')
    revenue_weight = Decimal('0.5')
    likes = user['likes']
    dislikes = user['dislikes']
    deals = user['deals_cnt']
    revenue_rub = user['deals_revenue']
    total = round(
        (likes * likes_weight + dislikes * dislikes_weight + deals * deals_weight) * revenue_rub * revenue_weight)
    sign = -1 if total < 0 else 1
    if total == 0:
        return 0
    result_rating = round(math.log(abs(total), 1.7) * sign)
    return result_rating


def _get_users(session):
    q = """
        SELECT id, deals_cnt, deals_revenue, total_likes as likes, total_dislikes as dislikes
        FROM "user" 
        WHERE last_action > NOW() - INTERVAL '3 hours' AND NOT is_temporary AND
            nickname NOT LIKE 'fd%' AND nickname NOT LIKE 'fs%'
    """
    return [dict(item) for item in session.execute(q).fetchall()]


def update_ratings():
    with session_scope() as session:
        users = _get_users(session)
        logger.info(f'users to update ratings {len(users)}')
    for user in users:
        rating = _get_rating_points(user)
        with session_scope() as session:
            session.execute(f'UPDATE "user" SET rating = {rating} WHERE id = {user["id"]};')
        time.sleep(0.5)
    logger.info(f'Ratings calculated')
