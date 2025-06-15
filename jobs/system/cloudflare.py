import json
import random
from string import ascii_letters, digits

from utils.db_sessions import session_scope

RANDOM_CHARS = ascii_letters + digits
ALGOS = ('b', 'e')


def get_new_mask():
    groups_count = random.randint(3, 15)
    random_mask_data = {
        ''.join(random.choices(RANDOM_CHARS, k=random.randint(5, 8))): ''.join(random.choices(RANDOM_CHARS, k=random.randint(3, 5)))
        for _ in range(groups_count)
    }
    random_mask_data['aKM'] = random.choice(ALGOS)
    return random_mask_data


def update_mask_db(mask, session):
    session.execute("UPDATE settings SET value = :val WHERE key = 'code_params'", {'val': json.dumps(mask)})


def update_code_data():
    new_mask = get_new_mask()
    with session_scope() as session:
        update_mask_db(new_mask, session)
