from datetime import datetime, timezone

from src.exceptions import DailyLimitExceededException
from src.models.pix import (
    TransferRequest,
    TransferResponse,
    TransferStatus,
)
from src.repository.interface import IPixRepository
from src.services.daily_limit_service import DailyLimitService
from src.services.idempotency_service import IdempotencyService
from src.services.transfer_audit_service import TransferAuditService


class PixService:
    def __init__(self, repository: IPixRepository) -> None:
        self.repository = repository
        self.idempotency = IdempotencyService(repository)
        self.daily_limit = DailyLimitService(repository)
        self.audit = TransferAuditService(repository)

    async def process_transfer(
        self, request: TransferRequest, idempotency_key: str
    ) -> TransferResponse:
        # Step 1: Idempotency cache check
        cached = await self.idempotency.get_cached_response(
            idempotency_key
        )
        if cached:
            return cached

        # Step 2: Acquire idempotency lock
        existing = await self.idempotency.acquire_lock(idempotency_key)
        if existing:
            return existing

        now_utc = datetime.now(timezone.utc)
        created_at_str = now_utc.isoformat()
        date_str = now_utc.strftime("%Y-%m-%d")

        # Step 3: Reserve daily limit
        status = await self.daily_limit.try_reserve(
            account_id=request.account_id,
            date_str=date_str,
            amount=request.amount,
            updated_at=created_at_str,
        )

        # Step 4: Build and persist transaction
        response = self.audit.build_response(
            request=request,
            status=status,
            created_at=created_at_str,
        )
        await self.audit.save(response)

        # Step 5: Save idempotency record
        if status != TransferStatus.APPROVED:
            error = DailyLimitExceededException()
            await self.idempotency.save_failure(
                idempotency_key, error
            )
            raise error

        await self.idempotency.save_success(
            idempotency_key, response
        )

        return response
