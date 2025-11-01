"""Daily P&L calculation service."""
from datetime import date, datetime, timedelta
from typing import Optional
import structlog

from app.services.mt5_manager import MT5ManagerService, Mt5DailyPnL, get_mt5_service

logger = structlog.get_logger()


class DailyPnLService:
    """Service for calculating daily P&L metrics."""

    def __init__(self, mt5_service: MT5ManagerService | None = None):
        self.mt5_service = mt5_service or get_mt5_service()

    async def calculate_daily_pnl(
        self,
        target_date: date,
        login: int
    ) -> Mt5DailyPnL | None:
        """
        Calculate daily P&L for an account using equity formula.
        
        Formula: equity_pnl = present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
        
        For date 31.10:
        - Fetches daily reports from 30.10 to 31.10
        - Uses 31.10 present_equity and equity_prev_day
        - Calculates net deposits/credits from deals on 31.10
        - Sums REB-tagged deals as rebate
        
        Args:
            target_date: The date to calculate P&L for (e.g., 2025-10-31)
            login: MT5 account login
            
        Returns:
            Mt5DailyPnL object or None if data not available
        """
        logger.info("calculating_daily_pnl", date=target_date, login=login)
        
        # Step 1: Fetch daily reports from (target_date - 1) to target_date
        # This ensures we get both previous day equity and current day equity
        prev_date = target_date - timedelta(days=1)
        
        daily_reports = await self.mt5_service.get_daily_reports(
            login=login,
            from_date=prev_date,
            to_date=target_date
        )
        
        if not daily_reports:
            logger.warning("no_daily_reports_for_pnl", login=login, target_date=target_date)
            return None
        
        # Find the report for target_date
        target_report = None
        for report in daily_reports:
            if report.date == target_date.strftime('%Y-%m-%d'):
                target_report = report
                break
        
        if not target_report:
            logger.warning("no_report_for_target_date", login=login, target_date=target_date)
            return None
        
        # Get present equity and equity_prev_day from the report
        present_equity = target_report.present_equity
        equity_prev_day = target_report.equity_prev_day
        
        # Step 2: Get deal history for target_date to calculate net_deposit, net_credit_promotion, rebate
        deal_history = await self.mt5_service.get_deal_history(
            login=login,
            from_date=target_date,
            to_date=target_date
        )
        
        # Calculate aggregates from deals using tag-based classification
        deposit = 0.0  # Deposits (DT-tagged)
        withdrawal = 0.0  # Withdrawals (WT-tagged)
        net_deposit = 0.0  # Net deposit (deposits - withdrawals)
        promotion = 0.0  # Promotions (everything else except REB)
        net_credit_promotion = 0.0  # Sum of credits/bonuses/charges
        rebate = 0.0  # Sum of rebates (REB-tagged deals)
        
        for deal in deal_history:
            # Classify based on tag (set by comment prefix)
            if deal.tag == "Deposit":
                deposit += abs(deal.amount)
                net_deposit += deal.amount
            elif deal.tag == "Withdrawal":
                withdrawal += abs(deal.amount)
                net_deposit += deal.amount  # Withdrawals are negative
            elif deal.tag == "Rebate":
                rebate += deal.amount
                net_credit_promotion += deal.amount
            elif deal.tag == "Promotion":
                promotion += abs(deal.amount) if deal.amount > 0 else 0
                net_credit_promotion += deal.amount
            else:
                # Fallback for any untagged deals
                if deal.action in ('DEPOSIT', 'WITHDRAWAL'):
                    net_deposit += deal.amount
                elif deal.action in ('CREDIT', 'CREDIT_OUT', 'CHARGE', 'CORRECTION'):
                    net_credit_promotion += deal.amount
        
        # Step 3: Get total IB commissions from daily report
        # MT5 stores IB commissions in daily_agent field
        total_ib = target_report.daily_agent if hasattr(target_report, 'daily_agent') else 0.0
        
        # Note: promotion is already calculated from deals above (promotion = sum of non-DT/WT/REB tagged deals)
        
        # Step 4: Calculate equity PNL using the formula
        # equity_pnl = present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
        equity_pnl = present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
        
        # Step 5: Calculate net PNL
        # net_pnl = equity_pnl - promotion
        net_pnl = equity_pnl - promotion
        
        logger.info("pnl_calculated", 
                   login=login, 
                   target_date=target_date,
                   present_equity=present_equity,
                   equity_prev_day=equity_prev_day,
                   net_deposit=net_deposit,
                   promotion=promotion,
                   net_credit_promotion=net_credit_promotion,
                   total_ib=total_ib,
                   rebate=rebate,
                   equity_pnl=equity_pnl,
                   net_pnl=net_pnl)
        
        return Mt5DailyPnL(
            login=login,
            date=target_date.strftime('%Y-%m-%d'),
            present_equity=present_equity,
            equity_prev_day=equity_prev_day,
            deposit=deposit,
            withdrawal=withdrawal,
            net_deposit=net_deposit,
            promotion=promotion,
            net_credit_promotion=net_credit_promotion,
            total_ib=total_ib,
            rebate=rebate,
            equity_pnl=equity_pnl,
            net_pnl=net_pnl,
            group=target_report.group,
            currency=target_report.currency,
        )

    async def calculate_date_range(
        self,
        from_date: date,
        to_date: date,
        login: int
    ) -> list[Mt5DailyPnL]:
        """
        Calculate daily P&L for a range of dates.
        
        Args:
            from_date: Start date
            to_date: End date
            login: MT5 account login
            
        Returns:
            List of Mt5DailyPnL objects
        """
        results = []
        current_date = from_date
        
        while current_date <= to_date:
            pnl = await self.calculate_daily_pnl(current_date, login)
            if pnl:
                results.append(pnl)
            current_date += timedelta(days=1)
        
        logger.info("date_range_pnl_calculated",
                   from_date=from_date,
                   to_date=to_date,
                   login=login,
                   total_days=len(results))
        
        return results

    async def calculate_all_logins_pnl(
        self,
        target_date: date
    ) -> list[Mt5DailyPnL]:
        """
        Calculate daily PNL for all accounts.
        
        Fetches daily reports for all accounts and calculates PNL for each.
        
        Args:
            target_date: The date to calculate P&L for
            
        Returns:
            List of Mt5DailyPnL objects (one per account)
        """
        logger.info("calculating_all_logins_pnl", target_date=target_date)
        
        # Step 1: Fetch daily reports for all accounts
        prev_date = target_date - timedelta(days=1)
        
        daily_reports = await self.mt5_service.get_daily_reports(
            login=None,  # Get all accounts
            from_date=prev_date,
            to_date=target_date
        )
        
        if not daily_reports:
            logger.warning("no_daily_reports_for_any_account", target_date=target_date)
            return []
        
        # Step 2: Group reports by login
        reports_by_login = {}
        for report in daily_reports:
            if report.date == target_date.strftime('%Y-%m-%d'):
                reports_by_login[report.login] = report
        
        logger.info("accounts_found_for_pnl", 
                   target_date=target_date, 
                   total_accounts=len(reports_by_login))
        
        # Step 3: Get deal history for target date (all accounts)
        deal_history = await self.mt5_service.get_deal_history(
            login=None,  # Get all accounts
            from_date=target_date,
            to_date=target_date
        )
        
        # Group deals by login
        deals_by_login = {}
        for deal in deal_history:
            if deal.login not in deals_by_login:
                deals_by_login[deal.login] = []
            deals_by_login[deal.login].append(deal)
        
        # Step 4: Calculate PNL for each account
        results = []
        for login, report in reports_by_login.items():
            try:
                # Get deals for this login
                login_deals = deals_by_login.get(login, [])
                
                # Calculate aggregates from deals using tag-based classification
                deposit = 0.0
                withdrawal = 0.0
                net_deposit = 0.0
                promotion = 0.0
                net_credit_promotion = 0.0
                rebate = 0.0
                
                for deal in login_deals:
                    # Classify based on tag (set by comment prefix)
                    if deal.tag == "Deposit":
                        deposit += abs(deal.amount)
                        net_deposit += deal.amount
                    elif deal.tag == "Withdrawal":
                        withdrawal += abs(deal.amount)
                        net_deposit += deal.amount  # Withdrawals are negative
                    elif deal.tag == "Rebate":
                        rebate += deal.amount
                        net_credit_promotion += deal.amount
                    elif deal.tag == "Promotion":
                        promotion += abs(deal.amount) if deal.amount > 0 else 0
                        net_credit_promotion += deal.amount
                    else:
                        # Fallback for any untagged deals
                        if deal.action in ('DEPOSIT', 'WITHDRAWAL'):
                            net_deposit += deal.amount
                        elif deal.action in ('CREDIT', 'CREDIT_OUT', 'CHARGE', 'CORRECTION'):
                            net_credit_promotion += deal.amount
                
                # Get values from report
                present_equity = report.present_equity
                equity_prev_day = report.equity_prev_day
                total_ib = report.daily_agent if hasattr(report, 'daily_agent') else 0.0
                
                # Calculate equity PNL
                equity_pnl = present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
                
                # Calculate net PNL
                net_pnl = equity_pnl - promotion
                
                results.append(Mt5DailyPnL(
                    login=login,
                    date=target_date.strftime('%Y-%m-%d'),
                    present_equity=present_equity,
                    equity_prev_day=equity_prev_day,
                    deposit=deposit,
                    withdrawal=withdrawal,
                    net_deposit=net_deposit,
                    promotion=promotion,
                    net_credit_promotion=net_credit_promotion,
                    total_ib=total_ib,
                    rebate=rebate,
                    equity_pnl=equity_pnl,
                    net_pnl=net_pnl,
                    group=report.group,
                    currency=report.currency,
                ))
            except Exception as e:
                logger.error("failed_to_calculate_pnl_for_login", 
                           login=login, 
                           target_date=target_date,
                           error=str(e))
                continue
        
        logger.info("all_logins_pnl_calculated", 
                   target_date=target_date,
                   total_accounts=len(results))
        
        return results

    def aggregate_institution_pnl(
        self,
        pnl_list: list[Mt5DailyPnL],
        target_date: date
    ) -> Mt5DailyPnL:
        """
        Aggregate all account PNLs into a single institution-wide record.
        
        Args:
            pnl_list: List of individual account PNL records
            target_date: The date for the aggregate
            
        Returns:
            Mt5DailyPnL object with login=0 representing institution total
        """
        if not pnl_list:
            return Mt5DailyPnL(
                login=0,  # 0 = institution total
                date=target_date.strftime('%Y-%m-%d'),
                present_equity=0.0,
                equity_prev_day=0.0,
                deposit=0.0,
                withdrawal=0.0,
                net_deposit=0.0,
                promotion=0.0,
                net_credit_promotion=0.0,
                total_ib=0.0,
                rebate=0.0,
                equity_pnl=0.0,
                net_pnl=0.0,
                group="ALL",
                currency="USD",
            )
        
        # Sum all fields
        total_present_equity = sum(pnl.present_equity for pnl in pnl_list)
        total_equity_prev_day = sum(pnl.equity_prev_day for pnl in pnl_list)
        total_deposit = sum(pnl.deposit for pnl in pnl_list)
        total_withdrawal = sum(pnl.withdrawal for pnl in pnl_list)
        total_net_deposit = sum(pnl.net_deposit for pnl in pnl_list)
        total_promotion = sum(pnl.promotion for pnl in pnl_list)
        total_net_credit_promotion = sum(pnl.net_credit_promotion for pnl in pnl_list)
        total_ib = sum(pnl.total_ib for pnl in pnl_list)
        total_rebate = sum(pnl.rebate for pnl in pnl_list)
        total_equity_pnl = sum(pnl.equity_pnl for pnl in pnl_list)
        total_net_pnl = sum(pnl.net_pnl for pnl in pnl_list)
        
        logger.info("institution_pnl_aggregated",
                   target_date=target_date,
                   total_accounts=len(pnl_list),
                   total_deposit=total_deposit,
                   total_withdrawal=total_withdrawal,
                   total_equity_pnl=total_equity_pnl,
                   total_net_pnl=total_net_pnl)
        
        return Mt5DailyPnL(
            login=0,  # 0 = institution total
            date=target_date.strftime('%Y-%m-%d'),
            present_equity=total_present_equity,
            equity_prev_day=total_equity_prev_day,
            deposit=total_deposit,
            withdrawal=total_withdrawal,
            net_deposit=total_net_deposit,
            promotion=total_promotion,
            net_credit_promotion=total_net_credit_promotion,
            total_ib=total_ib,
            rebate=total_rebate,
            equity_pnl=total_equity_pnl,
            net_pnl=total_net_pnl,
            group="ALL",
            currency="USD",
        )
