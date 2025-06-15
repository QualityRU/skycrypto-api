CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;

CREATE TYPE public.deal_state AS ENUM (
    'proposed',
    'confirmed',
    'paid',
    'closed',
    'deleted'
);

CREATE TYPE public.lot_type AS ENUM (
    'buy',
    'sell'
);

CREATE TYPE public.rights AS ENUM (
    'low',
    'high'
);

CREATE TYPE public.user_rate AS ENUM (
    'like',
    'dislike'
);

CREATE FUNCTION public.enforce_deal_count() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    deals_count INTEGER := 0;
BEGIN
    LOCK TABLE deal IN EXCLUSIVE MODE;

    SELECT INTO deals_count COUNT(*)
    FROM deal
    WHERE payment_id = NEW.payment_id AND state NOT IN ('closed', 'deleted');

    IF deals_count >= 1 THEN
        RAISE EXCEPTION 'Cannot insert more than 1 deal for this payment.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE FUNCTION public.trigger_set_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
              NEW.updated_at = NOW();
              RETURN NEW;
            END;
            $$;

CREATE TABLE public.accounts_join (
    id integer NOT NULL,
    account_web integer NOT NULL,
    account_tg integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    joined_at timestamp without time zone,
    confirmed boolean DEFAULT false,
    token text NOT NULL
);

CREATE SEQUENCE public.accounts_join_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.accounts_join_id_seq OWNED BY public.accounts_join.id;

CREATE TABLE public.baned_ip (
    ip character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 213 (class 1259 OID 1781306)
-- Name: broker; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broker (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name text NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    sky_pay boolean DEFAULT false NOT NULL,
    fast_deal boolean DEFAULT false NOT NULL,
    is_card boolean DEFAULT false NOT NULL,
    logo text
);


--
-- TOC entry 214 (class 1259 OID 1781317)
-- Name: broker_currency; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broker_currency (
    currency character varying(3) NOT NULL,
    broker_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 215 (class 1259 OID 1781340)
-- Name: campaign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campaign (
    id character varying(20) NOT NULL,
    name character varying(100) NOT NULL
);


--
-- TOC entry 216 (class 1259 OID 1781348)
-- Name: commissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.commissions (
    id integer NOT NULL,
    type text NOT NULL,
    symbol text,
    commission numeric(25,3) NOT NULL
);


--
-- TOC entry 217 (class 1259 OID 1781353)
-- Name: commissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.commissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3783 (class 0 OID 0)
-- Dependencies: 217
-- Name: commissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.commissions_id_seq OWNED BY public.commissions.id;


--
-- TOC entry 218 (class 1259 OID 1781354)
-- Name: cpayment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cpayment (
    id integer NOT NULL,
    user_id integer NOT NULL,
    merchant_id integer NOT NULL,
    private_key character varying(256),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    cpayment_id uuid NOT NULL,
    is_done boolean DEFAULT false NOT NULL,
    is_expired boolean DEFAULT false NOT NULL,
    amount numeric(15,8) NOT NULL,
    symbol character varying(4) NOT NULL,
    rate numeric(12,2) NOT NULL,
    commission numeric(15,8),
    amount_left numeric(15,8) DEFAULT 0 NOT NULL,
    amount_received numeric(15,8) DEFAULT 0 NOT NULL
);


--
-- TOC entry 219 (class 1259 OID 1781362)
-- Name: cpayment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cpayment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3784 (class 0 OID 0)
-- Dependencies: 219
-- Name: cpayment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cpayment_id_seq OWNED BY public.cpayment.id;


--
-- TOC entry 220 (class 1259 OID 1781374)
-- Name: crypto_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_settings (
    id integer NOT NULL,
    coin_name text NOT NULL,
    symbol text NOT NULL,
    tx_out_commission numeric(25,8) NOT NULL,
    min_tx_amount numeric(25,8) NOT NULL,
    withdraw_active boolean DEFAULT true,
    net_commission integer,
    buyer_commission numeric(5,4) DEFAULT 0.01 NOT NULL,
    seller_commission numeric(5,4) DEFAULT 0.005 NOT NULL,
    max_withdraw numeric(10,8) DEFAULT 1 NOT NULL
);


--
-- TOC entry 221 (class 1259 OID 1781383)
-- Name: crypto_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crypto_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3785 (class 0 OID 0)
-- Dependencies: 221
-- Name: crypto_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crypto_settings_id_seq OWNED BY public.crypto_settings.id;


--
-- TOC entry 222 (class 1259 OID 1781384)
-- Name: currency; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.currency (
    id character varying(3) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL,
    usd_rate numeric(10,4) DEFAULT 0 NOT NULL,
    rate_variation numeric(3,2) DEFAULT 0.15 NOT NULL
);


--
-- TOC entry 223 (class 1259 OID 1781391)
-- Name: deal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deal (
    id integer NOT NULL,
    identificator character varying(10) NOT NULL,
    amount_currency numeric(10,2) NOT NULL,
    amount_subunit numeric(25,0) NOT NULL,
    amount_subunit_frozen numeric(25,0) NOT NULL,
    buyer_id integer NOT NULL,
    seller_id integer NOT NULL,
    symbol character varying(4) NOT NULL,
    currency character varying(3) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    end_time timestamp without time zone,
    lot_id integer NOT NULL,
    rate numeric(14,2) NOT NULL,
    buyer_commission_subunits numeric(25,0) DEFAULT 0,
    seller_commission_subunits numeric(25,0) DEFAULT 0,
    referral_commission_buyer_subunits numeric(25,0) DEFAULT 0 NOT NULL,
    referral_commission_seller_subunits numeric(25,0) DEFAULT 0 NOT NULL,
    requisite character varying(2048) NOT NULL,
    state public.deal_state DEFAULT 'proposed'::public.deal_state,
    cancel_reason character varying(25),
    confirmed_at timestamp without time zone,
    type smallint DEFAULT 0 NOT NULL,
    address character(42),
    payment_id uuid,
    sell_id uuid,
    sale_v2_id uuid,
    ip character varying(20),
    payment_v2_id uuid
);


--
-- TOC entry 224 (class 1259 OID 1781403)
-- Name: deal_commissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deal_commissions (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    symbol character varying(4) NOT NULL,
    buyer_commission numeric(15,8) DEFAULT 0 NOT NULL,
    seller_commission numeric(15,8) DEFAULT 0 NOT NULL,
    referral_commission_buyer numeric(15,8) DEFAULT 0 NOT NULL,
    referral_commission_seller numeric(15,8) DEFAULT 0 NOT NULL,
    merchant_commission numeric(15,8) DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 225 (class 1259 OID 1781412)
-- Name: deal_commissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deal_commissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3786 (class 0 OID 0)
-- Dependencies: 225
-- Name: deal_commissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deal_commissions_id_seq OWNED BY public.deal_commissions.id;


--
-- TOC entry 226 (class 1259 OID 1781413)
-- Name: deal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3787 (class 0 OID 0)
-- Dependencies: 226
-- Name: deal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deal_id_seq OWNED BY public.deal.id;


--
-- TOC entry 227 (class 1259 OID 1781414)
-- Name: dispute; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispute (
    id integer NOT NULL,
    deal_id integer NOT NULL,
    initiator integer NOT NULL,
    opponent integer,
    is_closed boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    is_second_notification_sent boolean DEFAULT false NOT NULL
);


--
-- TOC entry 228 (class 1259 OID 1781420)
-- Name: dispute_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dispute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3788 (class 0 OID 0)
-- Dependencies: 228
-- Name: dispute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dispute_id_seq OWNED BY public.dispute.id;


--
-- TOC entry 229 (class 1259 OID 1781421)
-- Name: earnings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.earnings (
    id integer NOT NULL,
    symbol character varying(4) NOT NULL,
    controlled boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    income numeric(15,8)
);


--
-- TOC entry 230 (class 1259 OID 1781426)
-- Name: earnings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.earnings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3789 (class 0 OID 0)
-- Dependencies: 230
-- Name: earnings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.earnings_id_seq OWNED BY public.earnings.id;


--
-- TOC entry 231 (class 1259 OID 1781434)
-- Name: exchanges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exchanges (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id integer NOT NULL,
    from_symbol character varying(4) NOT NULL,
    to_symbol character varying(4) NOT NULL,
    rate numeric(10,2) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    amount_sent numeric(15,8) NOT NULL,
    commission numeric(15,8) DEFAULT 0,
    processed_at timestamp without time zone,
    amount_received numeric(15,8)
);


--
-- TOC entry 232 (class 1259 OID 1781440)
-- Name: insidetransaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.insidetransaction (
    id integer NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    controled boolean DEFAULT false NOT NULL,
    instance character(3) DEFAULT 'bot'::bpchar NOT NULL,
    balance numeric(30,8),
    frozen numeric(30,8),
    change_balance numeric(30,8),
    change_frozen numeric(30,8),
    user_id integer,
    symbol character varying(4)
);


--
-- TOC entry 233 (class 1259 OID 1781448)
-- Name: insidetransaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.insidetransaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3790 (class 0 OID 0)
-- Dependencies: 233
-- Name: insidetransaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.insidetransaction_id_seq OWNED BY public.insidetransaction.id;


--
-- TOC entry 234 (class 1259 OID 1781449)
-- Name: lot; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lot (
    id integer NOT NULL,
    identificator text NOT NULL,
    limit_from integer NOT NULL,
    limit_to integer NOT NULL,
    details text,
    rate numeric(20,2) NOT NULL,
    coefficient numeric(10,4),
    is_active boolean DEFAULT true NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    was_answered boolean DEFAULT true NOT NULL,
    user_id integer NOT NULL,
    symbol character varying(4) NOT NULL,
    currency character varying(3) NOT NULL,
    type public.lot_type NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    broker_id uuid
);


--
-- TOC entry 235 (class 1259 OID 1781458)
-- Name: lot_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3791 (class 0 OID 0)
-- Dependencies: 235
-- Name: lot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lot_id_seq OWNED BY public.lot.id;


--
-- TOC entry 236 (class 1259 OID 1781459)
-- Name: media; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.media (
    id integer NOT NULL,
    url text NOT NULL,
    loaded_by_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 237 (class 1259 OID 1781465)
-- Name: media_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.media_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3792 (class 0 OID 0)
-- Dependencies: 237
-- Name: media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.media_id_seq OWNED BY public.media.id;


--
-- TOC entry 238 (class 1259 OID 1781466)
-- Name: merchant; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.merchant (
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    user_id integer NOT NULL,
    name text NOT NULL,
    website text,
    image_url text,
    commission numeric(4,3) DEFAULT 0.01,
    callback_url character varying(512) DEFAULT NULL::character varying,
    is_active boolean DEFAULT false,
    commission_sale numeric(4,3) DEFAULT 0.01,
    is_active_sale boolean DEFAULT false,
    callback_url_sale character varying(512) DEFAULT NULL::character varying,
    callback_safe boolean DEFAULT false,
    is_active_withdrawal boolean DEFAULT false NOT NULL,
    required_mask boolean DEFAULT false NOT NULL,
    is_active_cpay boolean DEFAULT false,
    callback_url_cpay character varying(512) DEFAULT NULL::character varying,
    is_active_sky_pay_v2 boolean DEFAULT false NOT NULL,
    logo text
);


--
-- TOC entry 239 (class 1259 OID 1781500)
-- Name: notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification (
    id integer NOT NULL,
    user_id integer NOT NULL,
    symbol text NOT NULL,
    type text NOT NULL,
    telegram_notified boolean DEFAULT false NOT NULL,
    web_notified boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    deal_id integer,
    transaction_id integer,
    message_id integer,
    is_read boolean DEFAULT false,
    join_id integer,
    promocodeactivation_id integer,
    exchange_id uuid
);


--
-- TOC entry 240 (class 1259 OID 1781509)
-- Name: notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3793 (class 0 OID 0)
-- Dependencies: 240
-- Name: notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notification_id_seq OWNED BY public.notification.id;


--
-- TOC entry 241 (class 1259 OID 1781510)
-- Name: operations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operations (
    id character varying(128) NOT NULL,
    user_id integer NOT NULL,
    type smallint DEFAULT 1 NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    amount numeric(15,6) NOT NULL,
    symbol character varying(4) NOT NULL,
    action smallint NOT NULL,
    amount_currency numeric(10,2),
    commission numeric(12,8),
    label character varying(100),
    trader_commission numeric(8,2),
    commission_currency numeric(8,2),
    currency character varying(3) DEFAULT 'rub'::character varying
);


--
-- TOC entry 242 (class 1259 OID 1781538)
-- Name: profit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profit (
    symbol character varying(4) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    wallet_balance numeric(20,8) NOT NULL,
    users_balance numeric(20,8) NOT NULL,
    profit numeric(20,8) NOT NULL
);


--
-- TOC entry 243 (class 1259 OID 1781542)
-- Name: promocodeactivations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.promocodeactivations (
    id integer NOT NULL,
    wallet_id integer NOT NULL,
    promocode_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 244 (class 1259 OID 1781546)
-- Name: promocodeactivations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.promocodeactivations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3794 (class 0 OID 0)
-- Dependencies: 244
-- Name: promocodeactivations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.promocodeactivations_id_seq OWNED BY public.promocodeactivations.id;


--
-- TOC entry 245 (class 1259 OID 1781547)
-- Name: promocodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.promocodes (
    id integer NOT NULL,
    wallet_id integer NOT NULL,
    code text NOT NULL,
    amount numeric(25,0) NOT NULL,
    count smallint NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- TOC entry 246 (class 1259 OID 1781554)
-- Name: promocodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.promocodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3795 (class 0 OID 0)
-- Dependencies: 246
-- Name: promocodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.promocodes_id_seq OWNED BY public.promocodes.id;


--
-- TOC entry 247 (class 1259 OID 1781555)
-- Name: rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rates (
    symbol text NOT NULL,
    rate numeric(15,2) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    currency text NOT NULL
);


--
-- TOC entry 248 (class 1259 OID 1781571)
-- Name: secondarydeposits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secondarydeposits (
    id integer NOT NULL,
    tx_hash text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    controlled boolean DEFAULT false NOT NULL,
    amount numeric(15,8)
);


--
-- TOC entry 249 (class 1259 OID 1781578)
-- Name: secondarydeposits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secondarydeposits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3796 (class 0 OID 0)
-- Dependencies: 249
-- Name: secondarydeposits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secondarydeposits_id_seq OWNED BY public.secondarydeposits.id;


--
-- TOC entry 250 (class 1259 OID 1781591)
-- Name: settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.settings (
    key character varying(100) NOT NULL,
    value character varying(1000)
);


--
-- TOC entry 251 (class 1259 OID 1781607)
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id integer NOT NULL,
    wallet_id integer NOT NULL,
    type text NOT NULL,
    to_address text NOT NULL,
    amount_units numeric(25,18) NOT NULL,
    commission numeric(25,18) DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    processed_at timestamp without time zone,
    tx_hash text,
    is_confirmed boolean DEFAULT false NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    sky_commission numeric(15,8) DEFAULT 0.0002 NOT NULL,
    tx_type smallint DEFAULT 1 NOT NULL
);


--
-- TOC entry 252 (class 1259 OID 1781618)
-- Name: transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3797 (class 0 OID 0)
-- Dependencies: 252
-- Name: transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transactions_id_seq OWNED BY public.transactions.id;


--
-- TOC entry 253 (class 1259 OID 1781619)
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    telegram_id integer,
    lang text DEFAULT 'ru'::text NOT NULL,
    created_at date DEFAULT now() NOT NULL,
    currency character varying(3) DEFAULT 'rub'::text NOT NULL,
    nickname text NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    is_baned boolean DEFAULT false NOT NULL,
    is_verify boolean DEFAULT false NOT NULL,
    rights public.rights,
    email text,
    password text,
    code character(10),
    is_admin boolean DEFAULT false NOT NULL,
    last_action timestamp without time zone DEFAULT now() NOT NULL,
    likes integer DEFAULT 0 NOT NULL,
    dislikes integer DEFAULT 0 NOT NULL,
    rating integer DEFAULT 0 NOT NULL,
    secret text,
    otp_secret character(16),
    is_mfa_enabled boolean DEFAULT false NOT NULL,
    ref_kw character varying(10) DEFAULT ''::character varying NOT NULL,
    code_sent_at timestamp without time zone DEFAULT now(),
    receive_address character varying(100),
    receive_option integer,
    is_temporary boolean DEFAULT false NOT NULL,
    deals_cnt integer DEFAULT 0 NOT NULL,
    deals_revenue numeric(15,2) DEFAULT 0,
    allow_sell boolean DEFAULT false NOT NULL,
    allow_usdt boolean DEFAULT false NOT NULL,
    super_verify_only boolean DEFAULT false NOT NULL,
    stealth boolean DEFAULT false NOT NULL,
    total_likes integer DEFAULT 0 NOT NULL,
    total_dislikes integer DEFAULT 0 NOT NULL,
    sky_pay boolean DEFAULT false NOT NULL,
    allow_payment_v2 boolean DEFAULT false NOT NULL,
    shadow_ban boolean DEFAULT false NOT NULL,
    apply_shadow_ban boolean DEFAULT false NOT NULL
);


--
-- TOC entry 254 (class 1259 OID 1781651)
-- Name: user_campaign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_campaign (
    user_id integer NOT NULL,
    campaign_id character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- TOC entry 255 (class 1259 OID 1781655)
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3798 (class 0 OID 0)
-- Dependencies: 255
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- TOC entry 256 (class 1259 OID 1781656)
-- Name: userlogin_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.userlogin_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 257 (class 1259 OID 1781666)
-- Name: usermessage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usermessage (
    id integer NOT NULL,
    sender_id integer NOT NULL,
    receiver_id integer NOT NULL,
    message text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    symbol text NOT NULL,
    media_id integer,
    controled boolean DEFAULT false NOT NULL
);


--
-- TOC entry 258 (class 1259 OID 1781673)
-- Name: usermessage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usermessage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3799 (class 0 OID 0)
-- Dependencies: 258
-- Name: usermessage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usermessage_id_seq OWNED BY public.usermessage.id;


--
-- TOC entry 259 (class 1259 OID 1781674)
-- Name: usermessageban; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usermessageban (
    user_id integer NOT NULL,
    baned_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- TOC entry 260 (class 1259 OID 1781678)
-- Name: userrate; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.userrate (
    id integer NOT NULL,
    from_user_id integer NOT NULL,
    to_user_id integer NOT NULL,
    action public.user_rate NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    deal_id integer
);


--
-- TOC entry 261 (class 1259 OID 1781682)
-- Name: userrate_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.userrate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3800 (class 0 OID 0)
-- Dependencies: 261
-- Name: userrate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.userrate_id_seq OWNED BY public.userrate.id;


--
-- TOC entry 262 (class 1259 OID 1781683)
-- Name: wallet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wallet (
    id integer NOT NULL,
    user_id integer NOT NULL,
    symbol character varying(4) NOT NULL,
    balance numeric(25,0) DEFAULT 0 NOT NULL,
    frozen numeric(25,0) DEFAULT 0 NOT NULL,
    earned_from_ref numeric(25,0) DEFAULT 0 NOT NULL,
    private_key text,
    is_active boolean DEFAULT true NOT NULL,
    referred_from_id integer,
    total_received numeric(25,8) DEFAULT 0 NOT NULL,
    w_limit numeric(12,5),
    regenerate_wallet boolean DEFAULT false NOT NULL
);


--
-- TOC entry 263 (class 1259 OID 1781693)
-- Name: wallet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wallet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3801 (class 0 OID 0)
-- Dependencies: 263
-- Name: wallet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wallet_id_seq OWNED BY public.wallet.id;


--
-- TOC entry 264 (class 1259 OID 1781699)
-- Name: wthd; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wthd (
    id integer NOT NULL,
    tx_hash text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    controlled boolean DEFAULT false NOT NULL,
    amount numeric(15,8),
    symbol character varying(4) NOT NULL
);


--
-- TOC entry 265 (class 1259 OID 1781706)
-- Name: wthd_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wthd_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3802 (class 0 OID 0)
-- Dependencies: 265
-- Name: wthd_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wthd_id_seq OWNED BY public.wthd.id;


--
-- TOC entry 3344 (class 2604 OID 1781707)
-- Name: accounts_join id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_join ALTER COLUMN id SET DEFAULT nextval('public.accounts_join_id_seq'::regclass);


--
-- TOC entry 3353 (class 2604 OID 1781710)
-- Name: commissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.commissions ALTER COLUMN id SET DEFAULT nextval('public.commissions_id_seq'::regclass);


--
-- TOC entry 3359 (class 2604 OID 1781711)
-- Name: cpayment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpayment ALTER COLUMN id SET DEFAULT nextval('public.cpayment_id_seq'::regclass);


--
-- TOC entry 3364 (class 2604 OID 1781712)
-- Name: crypto_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_settings ALTER COLUMN id SET DEFAULT nextval('public.crypto_settings_id_seq'::regclass);


--
-- TOC entry 3376 (class 2604 OID 1781713)
-- Name: deal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal ALTER COLUMN id SET DEFAULT nextval('public.deal_id_seq'::regclass);


--
-- TOC entry 3383 (class 2604 OID 1781714)
-- Name: deal_commissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal_commissions ALTER COLUMN id SET DEFAULT nextval('public.deal_commissions_id_seq'::regclass);


--
-- TOC entry 3387 (class 2604 OID 1781715)
-- Name: dispute id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute ALTER COLUMN id SET DEFAULT nextval('public.dispute_id_seq'::regclass);


--
-- TOC entry 3390 (class 2604 OID 1781716)
-- Name: earnings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.earnings ALTER COLUMN id SET DEFAULT nextval('public.earnings_id_seq'::regclass);


--
-- TOC entry 3397 (class 2604 OID 1781718)
-- Name: insidetransaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insidetransaction ALTER COLUMN id SET DEFAULT nextval('public.insidetransaction_id_seq'::regclass);


--
-- TOC entry 3402 (class 2604 OID 1781719)
-- Name: lot id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lot ALTER COLUMN id SET DEFAULT nextval('public.lot_id_seq'::regclass);


--
-- TOC entry 3404 (class 2604 OID 1781720)
-- Name: media id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media ALTER COLUMN id SET DEFAULT nextval('public.media_id_seq'::regclass);


--
-- TOC entry 3422 (class 2604 OID 1781721)
-- Name: notification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification ALTER COLUMN id SET DEFAULT nextval('public.notification_id_seq'::regclass);


--
-- TOC entry 3428 (class 2604 OID 1781722)
-- Name: promocodeactivations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodeactivations ALTER COLUMN id SET DEFAULT nextval('public.promocodeactivations_id_seq'::regclass);


--
-- TOC entry 3431 (class 2604 OID 1781723)
-- Name: promocodes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodes ALTER COLUMN id SET DEFAULT nextval('public.promocodes_id_seq'::regclass);


--
-- TOC entry 3436 (class 2604 OID 1781724)
-- Name: secondarydeposits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secondarydeposits ALTER COLUMN id SET DEFAULT nextval('public.secondarydeposits_id_seq'::regclass);


--
-- TOC entry 3443 (class 2604 OID 1781726)
-- Name: transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions ALTER COLUMN id SET DEFAULT nextval('public.transactions_id_seq'::regclass);


--
-- TOC entry 3471 (class 2604 OID 1781727)
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- TOC entry 3475 (class 2604 OID 1781728)
-- Name: usermessage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessage ALTER COLUMN id SET DEFAULT nextval('public.usermessage_id_seq'::regclass);


--
-- TOC entry 3478 (class 2604 OID 1781729)
-- Name: userrate id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.userrate ALTER COLUMN id SET DEFAULT nextval('public.userrate_id_seq'::regclass);


--
-- TOC entry 3484 (class 2604 OID 1781730)
-- Name: wallet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet ALTER COLUMN id SET DEFAULT nextval('public.wallet_id_seq'::regclass);


--
-- TOC entry 3487 (class 2604 OID 1781731)
-- Name: wthd id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wthd ALTER COLUMN id SET DEFAULT nextval('public.wthd_id_seq'::regclass);


--
-- TOC entry 3489 (class 2606 OID 1781843)
-- Name: accounts_join accounts_join_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_join
    ADD CONSTRAINT accounts_join_pkey PRIMARY KEY (id);


--
-- TOC entry 3491 (class 2606 OID 1781849)
-- Name: baned_ip baned_ip_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.baned_ip
    ADD CONSTRAINT baned_ip_pkey PRIMARY KEY (ip);


--
-- TOC entry 3495 (class 2606 OID 1781855)
-- Name: broker_currency broker_currency_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_currency
    ADD CONSTRAINT broker_currency_pkey PRIMARY KEY (currency, broker_id);


--
-- TOC entry 3493 (class 2606 OID 1781857)
-- Name: broker broker_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker
    ADD CONSTRAINT broker_pkey PRIMARY KEY (id);


--
-- TOC entry 3497 (class 2606 OID 1781863)
-- Name: campaign campaign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaign
    ADD CONSTRAINT campaign_pkey PRIMARY KEY (id);


--
-- TOC entry 3552 (class 2606 OID 1781867)
-- Name: promocodes code_idx; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodes
    ADD CONSTRAINT code_idx UNIQUE (code);


--
-- TOC entry 3499 (class 2606 OID 1781869)
-- Name: commissions commissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.commissions
    ADD CONSTRAINT commissions_pkey PRIMARY KEY (id);


--
-- TOC entry 3502 (class 2606 OID 1781871)
-- Name: cpayment cpayment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpayment
    ADD CONSTRAINT cpayment_pkey PRIMARY KEY (id);


--
-- TOC entry 3504 (class 2606 OID 1781875)
-- Name: crypto_settings crypto_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_settings
    ADD CONSTRAINT crypto_settings_pkey PRIMARY KEY (id);


--
-- TOC entry 3506 (class 2606 OID 1781877)
-- Name: currency currency_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.currency
    ADD CONSTRAINT currency_pkey PRIMARY KEY (id);


--
-- TOC entry 3521 (class 2606 OID 1781879)
-- Name: deal_commissions deal_commissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal_commissions
    ADD CONSTRAINT deal_commissions_pkey PRIMARY KEY (id);


--
-- TOC entry 3515 (class 2606 OID 1781881)
-- Name: deal deal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal
    ADD CONSTRAINT deal_pkey PRIMARY KEY (id);


--
-- TOC entry 3524 (class 2606 OID 1781883)
-- Name: dispute dispute_deal_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute
    ADD CONSTRAINT dispute_deal_id_key UNIQUE (deal_id);


--
-- TOC entry 3527 (class 2606 OID 1781885)
-- Name: dispute dispute_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute
    ADD CONSTRAINT dispute_pkey PRIMARY KEY (id);


--
-- TOC entry 3529 (class 2606 OID 1781887)
-- Name: earnings earning_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earning_pkey PRIMARY KEY (id);


--
-- TOC entry 3532 (class 2606 OID 1781891)
-- Name: exchanges exchanges_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pk PRIMARY KEY (id);


--
-- TOC entry 3535 (class 2606 OID 1781893)
-- Name: insidetransaction insidetransaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insidetransaction
    ADD CONSTRAINT insidetransaction_pkey PRIMARY KEY (id);


--
-- TOC entry 3539 (class 2606 OID 1781895)
-- Name: lot lot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lot
    ADD CONSTRAINT lot_pkey PRIMARY KEY (id);


--
-- TOC entry 3541 (class 2606 OID 1781897)
-- Name: media media_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pkey PRIMARY KEY (id);


--
-- TOC entry 3543 (class 2606 OID 1781901)
-- Name: merchant merchant_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.merchant
    ADD CONSTRAINT merchant_pk PRIMARY KEY (user_id);


--
-- TOC entry 3546 (class 2606 OID 1781905)
-- Name: notification notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (id);


--
-- TOC entry 3554 (class 2606 OID 1781911)
-- Name: promocodes promocode_code_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodes
    ADD CONSTRAINT promocode_code_unique UNIQUE (code);


--
-- TOC entry 3550 (class 2606 OID 1781913)
-- Name: promocodeactivations promocodeactivations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodeactivations
    ADD CONSTRAINT promocodeactivations_pkey PRIMARY KEY (id);


--
-- TOC entry 3556 (class 2606 OID 1781915)
-- Name: promocodes promocodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodes
    ADD CONSTRAINT promocodes_pkey PRIMARY KEY (id);


--
-- TOC entry 3558 (class 2606 OID 1781917)
-- Name: rates rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rates
    ADD CONSTRAINT rates_pkey PRIMARY KEY (symbol, currency);


--
-- TOC entry 3560 (class 2606 OID 1781925)
-- Name: secondarydeposits secondarydeposit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secondarydeposits
    ADD CONSTRAINT secondarydeposit_pkey PRIMARY KEY (id);


--
-- TOC entry 3563 (class 2606 OID 1781929)
-- Name: settings settings_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pk PRIMARY KEY (key);


--
-- TOC entry 3565 (class 2606 OID 1781933)
-- Name: transactions transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transaction_pkey PRIMARY KEY (id);


--
-- TOC entry 3575 (class 2606 OID 1781935)
-- Name: user_campaign user_campaign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_campaign
    ADD CONSTRAINT user_campaign_pkey PRIMARY KEY (user_id, campaign_id);


--
-- TOC entry 3569 (class 2606 OID 1781937)
-- Name: user user_nickname_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_nickname_unique UNIQUE (nickname);


--
-- TOC entry 3571 (class 2606 OID 1781939)
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- TOC entry 3578 (class 2606 OID 1781943)
-- Name: usermessage usermessage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessage
    ADD CONSTRAINT usermessage_pkey PRIMARY KEY (id);


--
-- TOC entry 3583 (class 2606 OID 1781945)
-- Name: userrate userrate_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.userrate
    ADD CONSTRAINT userrate_pkey PRIMARY KEY (id);


--
-- TOC entry 3586 (class 2606 OID 1781947)
-- Name: wallet wallet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet
    ADD CONSTRAINT wallet_pkey PRIMARY KEY (id);


--
-- TOC entry 3588 (class 2606 OID 1781951)
-- Name: wthd wthd_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wthd
    ADD CONSTRAINT wthd_pkey PRIMARY KEY (id);


--
-- TOC entry 3500 (class 1259 OID 1781952)
-- Name: cpayment_cpayment_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX cpayment_cpayment_id_idx ON public.cpayment USING btree (cpayment_id);


--
-- TOC entry 3507 (class 1259 OID 1781953)
-- Name: deal_buyer_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_buyer_id_idx ON public.deal USING btree (buyer_id);


--
-- TOC entry 3519 (class 1259 OID 1781954)
-- Name: deal_commissions_deal_id_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX deal_commissions_deal_id_uindex ON public.deal_commissions USING btree (deal_id);


--
-- TOC entry 3508 (class 1259 OID 1781955)
-- Name: deal_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_created_at_idx ON public.deal USING btree (created_at);


--
-- TOC entry 3509 (class 1259 OID 1781956)
-- Name: deal_ident; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX deal_ident ON public.deal USING btree (identificator);


--
-- TOC entry 3510 (class 1259 OID 1781957)
-- Name: deal_identificator_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX deal_identificator_uindex ON public.deal USING btree (identificator);


--
-- TOC entry 3511 (class 1259 OID 1781958)
-- Name: deal_ip_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_ip_idx ON public.deal USING btree (ip);


--
-- TOC entry 3512 (class 1259 OID 1781960)
-- Name: deal_payment_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_payment_id_idx ON public.deal USING btree (payment_id);


--
-- TOC entry 3513 (class 1259 OID 1781963)
-- Name: deal_payment_id_idx1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_payment_id_idx1 ON public.deal USING btree (payment_id);


--
-- TOC entry 3516 (class 1259 OID 1781964)
-- Name: deal_sale_v2_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_sale_v2_id_idx ON public.deal USING btree (sale_v2_id);


--
-- TOC entry 3517 (class 1259 OID 1781965)
-- Name: deal_sell_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_sell_id_idx ON public.deal USING btree (sell_id);


--
-- TOC entry 3518 (class 1259 OID 1781966)
-- Name: deal_seller_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deal_seller_id_idx ON public.deal USING btree (seller_id);


--
-- TOC entry 3522 (class 1259 OID 1781968)
-- Name: dispute_deal_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dispute_deal_id_idx ON public.dispute USING btree (deal_id);


--
-- TOC entry 3525 (class 1259 OID 1781969)
-- Name: dispute_deal_id_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX dispute_deal_id_uindex ON public.dispute USING btree (deal_id);


--
-- TOC entry 3530 (class 1259 OID 1781970)
-- Name: earnings_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX earnings_created_at_idx ON public.earnings USING btree (created_at);


--
-- TOC entry 3533 (class 1259 OID 1781971)
-- Name: insidetransaction_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX insidetransaction_created_at_idx ON public.insidetransaction USING btree (created_at);


--
-- TOC entry 3536 (class 1259 OID 1781972)
-- Name: insidetransaction_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX insidetransaction_user_id_idx ON public.insidetransaction USING btree (user_id);


--
-- TOC entry 3537 (class 1259 OID 1781973)
-- Name: lot_broker_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX lot_broker_id_idx ON public.lot USING btree (broker_id);


--
-- TOC entry 3544 (class 1259 OID 1781975)
-- Name: merchant_user_id_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX merchant_user_id_uindex ON public.merchant USING btree (user_id);


--
-- TOC entry 3547 (class 1259 OID 1781976)
-- Name: notification_user_id_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notification_user_id_index ON public.notification USING btree (user_id);


--
-- TOC entry 3548 (class 1259 OID 1781977)
-- Name: operations_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX operations_user_id_idx ON public.operations USING btree (user_id);


--
-- TOC entry 3561 (class 1259 OID 1781981)
-- Name: settings_key_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX settings_key_uindex ON public.settings USING btree (key);


--
-- TOC entry 3566 (class 1259 OID 1781983)
-- Name: transactions_tx_hash_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX transactions_tx_hash_idx ON public.transactions USING btree (tx_hash);


--
-- TOC entry 3567 (class 1259 OID 1781994)
-- Name: user_email_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_email_idx ON public."user" USING btree (email);


--
-- TOC entry 3584 (class 1259 OID 1781995)
-- Name: user_id_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX user_id_symbol ON public.wallet USING btree (user_id, symbol);


--
-- TOC entry 3572 (class 1259 OID 1781996)
-- Name: user_telegram_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX user_telegram_id_idx ON public."user" USING btree (telegram_id);


--
-- TOC entry 3573 (class 1259 OID 1781997)
-- Name: user_telegram_id_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX user_telegram_id_uindex ON public."user" USING btree (telegram_id);


--
-- TOC entry 3576 (class 1259 OID 1781998)
-- Name: usermessage_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX usermessage_created_at_idx ON public.usermessage USING btree (created_at);


--
-- TOC entry 3579 (class 1259 OID 1781999)
-- Name: usermessage_receiver_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX usermessage_receiver_id_idx ON public.usermessage USING btree (receiver_id);


--
-- TOC entry 3580 (class 1259 OID 1782000)
-- Name: usermessage_sender_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX usermessage_sender_id_idx ON public.usermessage USING btree (sender_id);


--
-- TOC entry 3581 (class 1259 OID 1782001)
-- Name: userrate_deal_id_from_user_id_uindex; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX userrate_deal_id_from_user_id_uindex ON public.userrate USING btree (deal_id, from_user_id);


--
-- TOC entry 3637 (class 2620 OID 1782004)
-- Name: rates set_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER set_timestamp BEFORE UPDATE ON public.rates FOR EACH ROW EXECUTE FUNCTION public.trigger_set_timestamp();


--
-- TOC entry 3589 (class 2606 OID 1782005)
-- Name: accounts_join accounts_join_tg_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_join
    ADD CONSTRAINT accounts_join_tg_user_id_fkey FOREIGN KEY (account_tg) REFERENCES public."user"(id);


--
-- TOC entry 3590 (class 2606 OID 1782010)
-- Name: accounts_join accounts_join_web_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_join
    ADD CONSTRAINT accounts_join_web_user_id_fkey FOREIGN KEY (account_web) REFERENCES public."user"(id);


--
-- TOC entry 3630 (class 2606 OID 1782015)
-- Name: usermessageban baned_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessageban
    ADD CONSTRAINT baned_id_user_id_fkey FOREIGN KEY (baned_id) REFERENCES public."user"(id);


--
-- TOC entry 3591 (class 2606 OID 1782020)
-- Name: broker_currency broker_currency_broker_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_currency
    ADD CONSTRAINT broker_currency_broker_id_fk FOREIGN KEY (broker_id) REFERENCES public.broker(id);


--
-- TOC entry 3592 (class 2606 OID 1782025)
-- Name: broker_currency broker_currency_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_currency
    ADD CONSTRAINT broker_currency_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3593 (class 2606 OID 1782040)
-- Name: cpayment cpayment_merchant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpayment
    ADD CONSTRAINT cpayment_merchant_id_fkey FOREIGN KEY (merchant_id) REFERENCES public."user"(id);


--
-- TOC entry 3594 (class 2606 OID 1782045)
-- Name: cpayment cpayment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cpayment
    ADD CONSTRAINT cpayment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3595 (class 2606 OID 1782050)
-- Name: deal deal_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal
    ADD CONSTRAINT deal_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public."user"(id);


--
-- TOC entry 3599 (class 2606 OID 1782055)
-- Name: deal_commissions deal_commissions_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal_commissions
    ADD CONSTRAINT deal_commissions_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deal(id);


--
-- TOC entry 3596 (class 2606 OID 1782060)
-- Name: deal deal_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal
    ADD CONSTRAINT deal_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3597 (class 2606 OID 1782065)
-- Name: deal deal_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal
    ADD CONSTRAINT deal_lot_id_fkey FOREIGN KEY (lot_id) REFERENCES public.lot(id);


--
-- TOC entry 3598 (class 2606 OID 1782070)
-- Name: deal deal_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deal
    ADD CONSTRAINT deal_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public."user"(id);


--
-- TOC entry 3600 (class 2606 OID 1782075)
-- Name: dispute dispute_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute
    ADD CONSTRAINT dispute_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deal(id);


--
-- TOC entry 3601 (class 2606 OID 1782080)
-- Name: dispute dispute_initiator_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute
    ADD CONSTRAINT dispute_initiator_fkey FOREIGN KEY (initiator) REFERENCES public."user"(id);


--
-- TOC entry 3602 (class 2606 OID 1782085)
-- Name: dispute dispute_opponent_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute
    ADD CONSTRAINT dispute_opponent_fkey FOREIGN KEY (opponent) REFERENCES public."user"(id);


--
-- TOC entry 3603 (class 2606 OID 1782095)
-- Name: exchanges exchanges_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3632 (class 2606 OID 1782100)
-- Name: userrate from_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.userrate
    ADD CONSTRAINT from_user_id_fkey FOREIGN KEY (from_user_id) REFERENCES public."user"(id);


--
-- TOC entry 3604 (class 2606 OID 1782105)
-- Name: insidetransaction insidetransaction_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insidetransaction
    ADD CONSTRAINT insidetransaction_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3605 (class 2606 OID 1782110)
-- Name: lot lot_broker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lot
    ADD CONSTRAINT lot_broker_id_fkey FOREIGN KEY (broker_id) REFERENCES public.broker(id);


--
-- TOC entry 3606 (class 2606 OID 1782115)
-- Name: lot lot_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lot
    ADD CONSTRAINT lot_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3607 (class 2606 OID 1782120)
-- Name: lot lot_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lot
    ADD CONSTRAINT lot_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3608 (class 2606 OID 1782125)
-- Name: media media_loaded_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_loaded_by_id_fkey FOREIGN KEY (loaded_by_id) REFERENCES public."user"(id);


--
-- TOC entry 3609 (class 2606 OID 1782130)
-- Name: merchant merchant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.merchant
    ADD CONSTRAINT merchant_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3610 (class 2606 OID 1782135)
-- Name: notification notification_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deal(id);


--
-- TOC entry 3611 (class 2606 OID 1782140)
-- Name: notification notification_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id);


--
-- TOC entry 3612 (class 2606 OID 1782145)
-- Name: notification notification_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.usermessage(id);


--
-- TOC entry 3613 (class 2606 OID 1782150)
-- Name: notification notification_promocodeactivation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_promocodeactivation_id_fkey FOREIGN KEY (promocodeactivation_id) REFERENCES public.promocodeactivations(id);


--
-- TOC entry 3614 (class 2606 OID 1782155)
-- Name: notification notification_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id);


--
-- TOC entry 3615 (class 2606 OID 1782160)
-- Name: notification notification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3616 (class 2606 OID 1782165)
-- Name: notification notigication_accounts_join_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notigication_accounts_join_id_fkey FOREIGN KEY (join_id) REFERENCES public.accounts_join(id);


--
-- TOC entry 3633 (class 2606 OID 1782170)
-- Name: userrate on_deal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.userrate
    ADD CONSTRAINT on_deal_id_fkey FOREIGN KEY (deal_id) REFERENCES public.deal(id);


--
-- TOC entry 3617 (class 2606 OID 1782175)
-- Name: operations operations_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT operations_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3618 (class 2606 OID 1782180)
-- Name: operations operations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operations
    ADD CONSTRAINT operations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3619 (class 2606 OID 1782185)
-- Name: promocodeactivations promocodeactivations_promocode_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodeactivations
    ADD CONSTRAINT promocodeactivations_promocode_id_fkey FOREIGN KEY (promocode_id) REFERENCES public.promocodes(id);


--
-- TOC entry 3620 (class 2606 OID 1782190)
-- Name: promocodeactivations promocodeactivations_wallet_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodeactivations
    ADD CONSTRAINT promocodeactivations_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallet(id);


--
-- TOC entry 3621 (class 2606 OID 1782195)
-- Name: promocodes promocodes_wallet_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promocodes
    ADD CONSTRAINT promocodes_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallet(id);


--
-- TOC entry 3622 (class 2606 OID 1782200)
-- Name: rates rates_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rates
    ADD CONSTRAINT rates_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3627 (class 2606 OID 1782205)
-- Name: usermessage receiver_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessage
    ADD CONSTRAINT receiver_user_id_fkey FOREIGN KEY (receiver_id) REFERENCES public."user"(id);


--
-- TOC entry 3628 (class 2606 OID 1782220)
-- Name: usermessage sender_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessage
    ADD CONSTRAINT sender_user_id_fkey FOREIGN KEY (sender_id) REFERENCES public."user"(id);


--
-- TOC entry 3634 (class 2606 OID 1782225)
-- Name: userrate to_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.userrate
    ADD CONSTRAINT to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES public."user"(id);


--
-- TOC entry 3623 (class 2606 OID 1782230)
-- Name: transactions transaction_wallet_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transaction_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallet(id);


--
-- TOC entry 3625 (class 2606 OID 1782235)
-- Name: user_campaign user_campaign_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_campaign
    ADD CONSTRAINT user_campaign_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaign(id);


--
-- TOC entry 3626 (class 2606 OID 1782240)
-- Name: user_campaign user_campaign_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_campaign
    ADD CONSTRAINT user_campaign_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3624 (class 2606 OID 1782245)
-- Name: user user_currency_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_currency_id_fk FOREIGN KEY (currency) REFERENCES public.currency(id);


--
-- TOC entry 3631 (class 2606 OID 1782250)
-- Name: usermessageban user_id_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessageban
    ADD CONSTRAINT user_id_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- TOC entry 3629 (class 2606 OID 1782260)
-- Name: usermessage usermessage_media_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usermessage
    ADD CONSTRAINT usermessage_media_id_fkey FOREIGN KEY (media_id) REFERENCES public.media(id);


--
-- TOC entry 3635 (class 2606 OID 1782265)
-- Name: wallet wallet_referred_from_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet
    ADD CONSTRAINT wallet_referred_from_id_fkey FOREIGN KEY (referred_from_id) REFERENCES public."user"(id);


--
-- TOC entry 3636 (class 2606 OID 1782270)
-- Name: wallet wallet_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet
    ADD CONSTRAINT wallet_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
