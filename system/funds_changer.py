from crypto.manager import manager
from utils.utils import validate_amounts


def get_only_subunits(meth):
    def wrapper(*args, **kwargs):
        amount = kwargs.get('amount')
        symbol = kwargs.get('symbol')
        if amount:
            kwargs['amount_subunits'] = manager.to_subunit(symbol, amount)
        return meth(*args, **kwargs)
    return wrapper


def _change_funds(*, user_id, symbol, msg, session, change_balance_subunits=0, change_frozen_subunits=0):
    q1 = """
        SELECT balance, frozen
        FROM wallet 
        WHERE user_id = :uid AND symbol = :sym
    """
    b, f = session.execute(q1, {'uid': user_id, 'sym': symbol}).fetchone()
    if b + change_balance_subunits < 0 or f + change_frozen_subunits < 0:
        raise Exception(f'balance or frozen < 0, msg = {msg}, user_id = {user_id}')

    q = """
        UPDATE wallet 
        SET balance = balance + :bal_amount, frozen = frozen + :frozen_amount
        WHERE user_id = :uid AND symbol = :sym
        RETURNING id, balance, frozen;
    """
    wallet_id, new_balance, new_frozen = session.execute(
        q, {
            'bal_amount': change_balance_subunits,
            'frozen_amount': change_frozen_subunits,
            'uid': user_id,
            'sym': symbol
        }
    ).fetchone()
    if new_balance < 0 or new_frozen < 0:
        nick = session.execute('SELECT nickname FROM "user" WHERE id = :uid', {'uid': user_id}).scalar()
        raise ValueError(f'User /u{nick} frozen < 0, {msg}')
    new_balance = manager.from_subunit(symbol, new_balance)
    new_frozen = manager.from_subunit(symbol, new_frozen)
    change_balance_amount = manager.from_subunit(symbol, change_balance_subunits)
    change_frozen_amount = manager.from_subunit(symbol, change_frozen_subunits)
    q = """
        INSERT INTO insidetransaction (message, balance, frozen, change_balance, change_frozen, user_id, symbol)
        VALUES (:msg, :bal, :frozen, :change_bal, :change_frozen, :uid, :sym) 
    """
    session.execute(
        q, {
            'msg': msg,
            'bal': new_balance,
            'frozen': new_frozen,
            'change_bal': change_balance_amount,
            'change_frozen': change_frozen_amount,
            'sym': symbol,
            'uid': user_id
        }
    )


@validate_amounts
@get_only_subunits
def change_balance(user_id, msg, *, symbol, amount_subunits=None, session, **kwargs):
    _change_funds(user_id=user_id, symbol=symbol, msg=msg, session=session, change_balance_subunits=amount_subunits)


@validate_amounts
@get_only_subunits
def change_frozen(user_id, msg, *, symbol, amount_subunits=None, session, **kwargs):
    _change_funds(user_id=user_id, symbol=symbol, msg=msg, session=session, change_frozen_subunits=amount_subunits)


@validate_amounts
@get_only_subunits
def freeze(user_id, msg, *, symbol, amount_subunits=None, session, **kwargs):
    _change_funds(user_id=user_id, symbol=symbol, msg=msg, session=session,
                  change_balance_subunits=-amount_subunits, change_frozen_subunits=amount_subunits)


@validate_amounts
@get_only_subunits
def unfreeze(user_id, msg, *, symbol, amount_subunits=None, session, **kwargs):
    _change_funds(user_id=user_id, symbol=symbol, msg=msg, session=session,
                  change_frozen_subunits=-amount_subunits, change_balance_subunits=amount_subunits)
