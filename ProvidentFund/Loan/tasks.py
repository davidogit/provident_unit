from decimal import ROUND_HALF_UP, Decimal
import logging
from django.utils.timezone import now
from datetime import timedelta
from .models import LoanApplication
from django.db import transaction
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(bind=True)
def accrue_interest_daily(self):
    today = now().date()
    all_loans = LoanApplication.objects.filter(
        status='Disbursed'
    )
    logger.info(f'All Loans: {all_loans}')

    updated_loans = []

    with transaction.atomic():
        for loan in all_loans:
            if loan.last_interest_accrual_date == today:
                continue
            
            # logger.info(f'Current Loan: {loan}')
            days_elapsed = Decimal((today - loan.last_interest_accrual_date).days) if loan.last_interest_accrual_date else Decimal(1)

            annual_rate = loan.loan_type.loan_interest_rate/100
            daily_rate = annual_rate/365

            # logger.info(f'Loan Type: {loan.loan_type.interest_calculation_type}')

            # logger.info(f'Principal: {loan.amount_requested}, Daily Rate: {daily_rate}, Days Elapsed: {days_elapsed}')

            if loan.loan_type.interest_calculation_type == 'FLAT':
                daily_interest_accrued = loan.amount_requested*daily_rate*days_elapsed
            elif loan.loan_type.interest_calculation_type == 'REDUCING':
                daily_interest_accrued = loan.remaining_principal*daily_rate*days_elapsed
            else:
                continue

            # log_result = daily_interest_accrued.quantize(Decimal('0.01'),ROUND_HALF_UP)
            # logger.info(f'Daily interest for loan: {loan} for: {log_result}')
            loan.accrued_interest_to_date += daily_interest_accrued.quantize(Decimal("0.01"), ROUND_HALF_UP)
            loan.last_interest_accrual_date = today

            updated_loans.append(loan)

        LoanApplication.objects.bulk_update(updated_loans, ['accrued_interest_to_date', 'last_interest_accrual_date'])