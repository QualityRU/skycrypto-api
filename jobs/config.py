from datetime import datetime, timedelta


class Config:
    JOBS = [
        # ETH
        {
            'id': 'ETH Deposit',
            'func': 'jobs.transactions.deposit.eth_and_erc20:deposit',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'ETH Deposit check tx',
            'func': 'jobs.transactions.deposit.eth_and_erc20:check_tx',
            'trigger': 'interval',
            'seconds': 45,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'ETH Withdraw',
            'func': 'jobs.transactions.withdraw.eth:send_withdraw_tx',
            'trigger': 'interval',
            'seconds': 10,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'ETH Withdraw check tx',
            'func': 'jobs.transactions.withdraw.eth:check_tx',
            'trigger': 'interval',
            'seconds': 10,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },

        # USDT
        {
            'id': 'USDT Deposit',
            'func': 'jobs.transactions.deposit.usdt_trx:deposit',
            'trigger': 'interval',
            'minutes': 2,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'USDT Withdraw',
            'func': 'jobs.transactions.withdraw.usdt:send_withdraw_tx',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        # {
        #     'id': 'TRX FREEZE',
        #     'func': 'jobs.transactions.freeze_trx:freeze_trx',
        #     'trigger': 'interval',
        #     'hours': 1,
        #     'max_instances': 1,
        #     'next_run_time': datetime.now() + timedelta(seconds=3)
        # },

        # BTC
        {
            'id': 'BTC Deposit',
            'func': 'jobs.transactions.deposit.btc:deposit',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },
        {
            'id': 'BTC Withdraw',
            'func': 'jobs.transactions.withdraw.btc:withdraw',
            'trigger': 'interval',
            'minutes': 10,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=10)
        },
        {
            'id': 'UTXO CONSOLIDATION',
            'func': 'jobs.transactions.utxo_consolidation:consolidate',
            'trigger': 'interval',
            'hours': 6,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },



        # DEALS
        {
            'id': 'Deals update',
            'func': 'jobs.deals.timeout:update_deals',
            'trigger': 'interval',
            'seconds': 5,
            'max_instances': 1
        },


        # DISPUTES
        {
            'id': 'Check disputes',
            'func': 'jobs.deals.disputes:update_disputes',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },
        {
            'id': 'Disputes notification',
            'func': 'jobs.deals.disputes_notification:process_dispute_updates',
            'trigger': 'interval',
            'seconds': 29,
            'max_instances': 1
        },

        # RATES
        {
            'id': 'Rates update',
            'func': 'jobs.rates.update:update_rates',
            'trigger': 'interval',
            'minutes': 5,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'Currency rates update',
            'func': 'jobs.rates.update_currency_rates:update',
            'trigger': 'interval',
            'hours': 24,
            'max_instances': 1,
            # 'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'Rates V2 update',
            'func': 'jobs.rates.update_v2:update_v2_rates',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'Brokers V2 update',
            'func': 'jobs.brokers.update_brokers_v2:update_brokers',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },
        {
            'id': 'Actual rates V2 update',
            'func': 'jobs.rates.update_v2:update_v2_actual_rates',
            'trigger': 'interval',
            'minutes': 5,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=3)
        },

        # RATING
        {
            'id': 'Ratings update',
            'func': 'jobs.ratings.update:update_ratings',
            'trigger': 'interval',
            'hours': 3,
            'max_instances': 1,
            # 'next_run_time': datetime.now() + timedelta(seconds=15)
        },

        # LIKES
        {
            'id': 'Likes update',
            'func': 'jobs.ratings.update_likes:update_likes',
            'trigger': 'interval',
            'hours': 1,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=50)
        },

        # DEALS_CNT
        {
            'id': 'Deals cnt update',
            'func': 'jobs.ratings.update_deals_cnt:update_deals_cnt',
            'trigger': 'interval',
            'hours': 3,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=5)
        },

        # LOTS
        {
            'id': 'Lots update',
            'func': 'jobs.lots.update_rate:update_lots',
            'trigger': 'interval',
            'minutes': 2,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=5)
        },

        # SECONDARY NODE MANAGEMENT
        {
            'id': 'Balance update',
            'func': 'jobs.secondary_node_management.update_balance:update',
            'trigger': 'interval',
            'minutes': 2,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=5)
        },

        # AUTO WITHDRAWALS
        # {
        #     'id': 'Auto withdrawal',
        #     'func': 'jobs.system.autowithdrawal:auto_withdraw',
        #     'trigger': 'interval',
        #     'minutes': 5,
        #     'max_instances': 1,
        #     'next_run_time': datetime.now() + timedelta(seconds=5)
        # },

        # CPAYMENTS
        {
            'id': 'Process cpayments',
            'func': 'jobs.cpayments.process_cpayments:process_cpayments_v2',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1,
            'next_run_time': datetime.now() + timedelta(seconds=5)
        },

        # PROFIT
        {
            'id': 'Profit writer',
            'func': 'jobs.profit.profit:update_profit',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1,
        },

        # CLEAN
        {
            'id': 'Notifications cleaner',
            'func': 'jobs.notifications.cleaner:clean',
            'trigger': 'interval',
            'minutes': 5,
            'max_instances': 1,
        },

        # DEPRECATE PAYMENTS
        {
            'id': 'Deprecate old payments',
            'func': 'jobs.payments.deprecate_payments_trigger:deprecate_payments_trigger',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1
        },
        {
            'id': 'Deprecate old payments_v2',
            'func': 'jobs.payment_v2.deprecate_payments_trigger:deprecate_payments_v2_trigger',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1
        },

        # UPDATE MERCHANTS
        {
            'id': 'Update merchants',
            'func': 'jobs.merchants.update_merchants:update_v2_merchants',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1
        },

        # SELLS
        {
            'id': 'Validate sells',
            'func': 'jobs.sells.process_sell:process_sells',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1
        },
        {
            'id': 'Deprecate sells',
            'func': 'jobs.sells.return_funds:return_funds',
            'trigger': 'interval',
            'seconds': 21,
            'max_instances': 1
        },
        {
            'id': 'Deprecate inactive sells',
            'func': 'jobs.sells.deprecate_sales:deprecate_sales',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1
        },

        # SALE V2
        {
            'id': 'Process sale v2',
            'func': 'jobs.sale_v2.process_sale_v2:process_sale_v2',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },

        # PAYMENT V2
        {
            'id': 'Process payments v2',
            'func': 'jobs.payment_v2.process_payments_v2:process_payments_v2',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },
        {
            'id': 'Confirm payments v2',
            'func': 'jobs.payment_v2.confirm_payments_v2:confirm_payments_v2',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },

        # WITHDRAWAL V2
        {
            'id': 'Process withdrawal v2',
            'func': 'jobs.withdrawals_v2.process_withdrawal_v2:process_withdrawal_v2',
            'trigger': 'interval',
            'seconds': 30,
            'max_instances': 1
        },

        # FROZEN
        {
            'id': 'Control frozen',
            'func': 'jobs.control.frozen_control:control',
            'trigger': 'interval',
            'minutes': 5,
            'max_instances': 1
        },

        # IP
        {
            'id': 'Ban IP',
            'func': 'jobs.system.autoban_ip:ban_ips',
            'trigger': 'interval',
            'minutes': 1,
            'max_instances': 1
        },

        # SECURITY
        {
            'id': 'Change Cloudflare mask',
            'func': 'jobs.system.cloudflare:update_code_data',
            'trigger': 'interval',
            'seconds': 15,
            'max_instances': 1
        }
    ]

    SCHEDULER_API_ENABLED = True
