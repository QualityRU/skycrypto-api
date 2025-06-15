import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from uuid import UUID

from system.settings import metadata

metadata.reflect()

users_table = metadata.tables["user"]
wallets_table = metadata.tables["wallet"]
deals_table = metadata.tables["deal"]
lots_table = metadata.tables["lot"]
brokers_table = metadata.tables["broker"]
currencies_table = metadata.tables["currency"]
broker_currencies_table = metadata.tables["broker_currency"]
rates_table = metadata.tables["rates"]
promo_codes_table = metadata.tables["promocodes"]
crypto_settings_table = metadata.tables["crypto_settings"]
settings_table = metadata.tables["settings"]
transactions_table = metadata.tables["transactions"]
disputes_table = metadata.tables["dispute"]
operations_table = metadata.tables["operations"]
notifications_table = metadata.tables["notification"]
deal_commissions_table = metadata.tables["deal_commissions"]
merchant_table = metadata.tables["merchant"]
commissions_table = metadata.tables["commissions"]

@dataclass
class CurrencyDTO:
    id: str
    created_at: datetime
    is_active: bool
    usd_rate: Decimal
    rate_variation: Decimal


@dataclass
class RateDTO:
    symbol: str
    rate: Decimal
    created_at: datetime
    updated_at: datetime
    currency: str


@dataclass
class UserDTO:
    id: int
    telegram_id: int
    lang: str
    created_at: datetime
    currency: str
    nickname: str
    is_deleted: bool
    is_baned: bool
    is_verify: bool
    rights: Optional[Any]
    email: Optional[str]
    password: Optional[str]
    code: Optional[str]
    is_admin: bool
    last_action: datetime
    likes: int
    dislikes: int
    rating: int
    secret: Optional[str]
    otp_secret: Optional[str]
    is_mfa_enabled: bool
    ref_kw: str
    code_sent_at: Optional[datetime]
    receive_address: Optional[str]
    receive_option: Optional[str]
    is_temporary: bool
    deals_cnt: int
    deals_revenue: Optional[Decimal]
    allow_sell: bool
    allow_usdt: bool
    super_verify_only: bool
    stealth: bool
    total_likes: int
    total_dislikes: int
    sky_pay: bool
    allow_payment_v2: bool
    shadow_ban: bool
    apply_shadow_ban: bool


@dataclass
class WalletDTO:
    id: int
    user_id: int
    symbol: str
    balance: Decimal
    frozen: Decimal
    earned_from_ref: Decimal
    private_key: str
    is_active: bool
    referred_from_id: Optional[int]
    total_received: Decimal
    w_limit: Optional[Decimal]
    regenerate_wallet: bool


@dataclass
class BrokerDTO:
    id: UUID
    name: str
    is_deleted: str
    created_at: datetime
    sky_pay: bool
    fast_deal: bool
    is_card: bool
    logo: Optional[str]


@dataclass
class BrokerCurrencyDTO:
    currency: str
    broker_id: UUID
    created_at: datetime


@dataclass
class LotDTO:
    id: int
    identificator: str
    limit_from: int
    limit_to: int
    details: Optional[str]
    rate: Decimal
    coefficient: Optional[Decimal]
    is_active: bool
    is_deleted: bool
    was_answered: bool
    user_id: int
    symbol: str
    currency: str
    type: str
    created_at: datetime
    broker_id: Optional[str]


@dataclass
class DealDTO:
    id: int
    identificator: str
    amount_currency: Decimal
    amount_subunit: Decimal
    amount_subunit_frozen: Decimal
    buyer_id: int
    seller_id: int
    symbol: str
    currency: str
    created_at: datetime
    end_time: Optional[datetime]
    lot_id: int
    rate: Decimal
    buyer_commission_subunits: Decimal
    seller_commission_subunits: Decimal
    referral_commission_buyer_subunits: Decimal
    referral_commission_seller_subunits: Decimal
    requisite: str
    state: str
    cancel_reason: Optional[str]
    confirmed_at: Optional[datetime]
    type: int
    address: Optional[str]
    payment_id: Optional[UUID]
    sell_id: Optional[UUID]
    sale_v2_id: Optional[UUID]
    ip: Optional[str]
    payment_v2_id: Optional[UUID]


@dataclass
class PromoCodeDTO:
    id: int
    wallet_id: int
    code: str
    amount: int
    count: int
    is_deleted: bool
    created_at: datetime


@dataclass
class CryptoSettingsDTO:
    id: int
    coin_name: str
    symbol: str
    tx_out_commission: Decimal
    min_tx_amount: Decimal
    withdraw_active: bool
    net_commission: int
    buyer_commission: Decimal
    seller_commission: Decimal
    max_withdraw: Decimal

@dataclass
class SettingsDTO:
    key: str
    value: str


@dataclass
class DisputeDTO:
    id: int
    deal_id: int
    initiator: int
    opponent: int
    is_closed: bool
    created_at: datetime
    is_second_notification_sent: bool


@dataclass
class OperationDTO:
    id: str
    user_id: int
    type: int
    created_at: datetime
    amount: Decimal
    symbol: str
    action: int
    amount_currency: Decimal
    commission: Decimal
    label: str
    trader_commission: Decimal
    commission_currency: Decimal
    currency: str


@dataclass
class NotificationDTO:
    id: int
    user_id: int
    symbol: str
    type: str
    telegram_notified: bool
    web_notified: bool
    created_at: datetime
    deal_id: int
    transaction_id: int
    message_id: int
    is_read: bool
    join_id: int
    promocodeactivation_id: int
    exchange_id: UUID


@dataclass
class DealCommissionDTO:
    id: int
    deal_id: int
    symbol: str
    buyer_commission: Decimal
    seller_commission: Decimal
    referral_commission_buyer: Decimal
    referral_commission_seller: Decimal
    merchant_commission: Decimal
    created_at: datetime


@dataclass
class TransactionDTO:
    id: int
    wallet_id: int
    type: str
    to_address: str
    amount_units: Decimal
    commission: Decimal
    created_at: datetime
    processed_at: datetime
    tx_hash: str
    is_confirmed: bool
    is_deleted: bool
    sky_commission: Decimal
    tx_type: int

@dataclass
class MerchantDTO:
    created_at: datetime
    user_id: int
    name: str
    website: str
    image_url: str
    commission: Decimal
    callback_url: str
    is_active: bool
    commission_sale: Decimal
    is_active_sale: bool
    callback_url_sale: bool
    callback_safe:bool
    is_active_withdrawal: bool
    required_mask: bool
    is_active_cpay: bool
    callback_url_cpay: str
    is_active_sky_pay_v2: bool
    logo: str

@dataclass
class CommissionDTO:
    id: int
    type: str
    symbol: str
    commission: Decimal