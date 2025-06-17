import json
import logging
from datetime import datetime
from os import environ
from dotenv import load_dotenv
load_dotenv()

from pika import URLParameters, BlockingConnection

from system.constants import STATES
from utils.logger import logger

url = environ.get('CLOUDAMQP_URL')
params = URLParameters(url)
params.socket_timeout = 5

logging.getLogger("pika").setLevel(logging.WARNING)


def _send_queue_notification(user_id, data):
    logger.info(f'Sending message to {user_id}, {data}')
    with BlockingConnection(params) as connection:
        channel = connection.channel()
        q = f'updates_{user_id}'
        try:
            channel.queue_declare(queue=q, auto_delete=True)
        except Exception as e:
            if 'PRECONDITION_FAILED' in str(e):
                channel = connection.channel()
                channel.queue_delete(queue=q)
                channel.queue_declare(queue=q, auto_delete=True)

        channel.basic_publish(exchange='', routing_key=q, body=json.dumps(data).encode())
        print("[x] Message sent to consumer")


def send_notification_to_queue(user_id, data):
    try:
        _send_queue_notification(user_id, data)
    except Exception as e:
        logger.exception(e)


def _get_deal_details(user_id, deal_id, session):
    q = """
                SELECT d.identificator, state, user_id, d.symbol
                FROM deal d
                LEFT JOIN lot l on d.lot_id = l.id
                WHERE d.id = :did
            """
    identificator, state, creator_id, symbol = session.execute(q, {'did': deal_id}).fetchone()
    details = {'id': identificator, 'state': state, 'is_owner': creator_id == user_id}
    return details, symbol


def create_deal_notification(user_id, deal_id: int, session, n_type='deal'):
    details, symbol = _get_deal_details(user_id, deal_id, session)
    notification_id = session.execute(
        """
            INSERT INTO notification (user_id, symbol, type, deal_id)
            VALUES (:opp, :sym, :t, :did)
            RETURNING id
        """, {'opp': user_id, 'sym': symbol, 'did': deal_id, 't': n_type}
    ).scalar()
    send_notification_to_queue(
        user_id,
        {
            'id': notification_id,
            'type': n_type,
            'details': details,
            'created_at': round(datetime.utcnow().timestamp())
        }
    )


def create_timeout_notification(user_id, symbol, deal_id, identificator, session):
    notification_id = session.execute(
        f"""
            INSERT INTO notification (user_id, symbol, type, deal_id)
            VALUES ({user_id}, '{symbol}', 'timeout', {deal_id})
            RETURNING id
        """
    ).scalar()
    send_notification_to_queue(
        user_id,
        {
            'id': notification_id,
            'type': 'timeout',
            'details': {'id': identificator},
            'created_at': round(datetime.utcnow().timestamp())
        }
    )


def create_closed_dispute_notification(user_id, symbol, deal_id, session, admin=False):
    q = """
        INSERT INTO notification (user_id, symbol, type, deal_id)
        VALUES (:uid, :sym, :t, :did)
        RETURNING id
    """
    t = 'closed_dispute'
    if admin:
        t += '_admin'
    notification_id = session.execute(q, {'uid': user_id, 'sym': symbol, 'did': deal_id, 't': t}).scalar()
    identificator, state = session.execute(
        'SELECT identificator, state FROM deal WHERE id = :did LIMIT 1',
        {'did': deal_id}
    ).fetchone()
    winner = 'seller' if state == STATES[-1] else 'buyer'
    send_notification_to_queue(
        user_id,
        {
            'id': notification_id,
            'type': t,
            'details': {'id': identificator, 'winner': winner},
            'created_at': round(datetime.utcnow().timestamp())
        }
    )


def create_message_notification(user_id, sender_id, message, message_id: int, media_id, symbol, session):
    sender_nickname = session.execute('SELECT nickname FROM "user" WHERE id = :uid LIMIT 1', {'uid': sender_id}).scalar()
    q = """
            INSERT INTO notification (user_id, symbol, type, message_id) 
            VALUES (:receiver_id, :symbol, 'message', :message_id)
            RETURNING id
        """
    notification_id = session.execute(q, {'receiver_id': user_id, 'message_id': message_id, 'symbol': symbol}).scalar()
    send_notification_to_queue(
        user_id,
        {
            'id': notification_id,
            'type': 'message',
            'details': {'sender': sender_nickname, 'text': message, 'media_id': media_id},
            'created_at': round(datetime.utcnow().timestamp())
        }
    )

