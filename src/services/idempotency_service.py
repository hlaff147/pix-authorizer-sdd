from typing import Optional

from src.exceptions import DailyLimitExceededException
from src.models.pix import TransferResponse
from src.repository.interface import IPixRepository


class IdempotencyService:
    """Handles idempotency check, lock acquisition, and record persistence."""

    def __init__(self, repository: IPixRepository) -> None:
        self.repository = repository

    async def get_cached_response(
        self, idempotency_key: str
    ) -> Optional[TransferResponse]:
        """Step 1: Check if a cached response exists for this key.

        Returns TransferResponse on cache hit (success),
        raises DailyLimitExceededException on cache hit (failure),
        or returns None on cache miss.
        """
        cached_record = await self.repository.get_idempotency_record(
            idempotency_key
        )
        if not cached_record:
            return None

        status_code = cached_record["response_status"]
        body = cached_record["response_body"]

        if status_code == 400:
            raise DailyLimitExceededException(
                message=body.get("message", "Limite diário excedido")
            )
        return TransferResponse(**body)

    async def acquire_lock(
        self, idempotency_key: str
    ) -> Optional[TransferResponse]:
        """Step 2: Try to acquire the idempotency lock.

        Returns None if lock was acquired (caller should proceed).
        Returns TransferResponse if another request already completed.
        Raises DailyLimitExceededException if in-progress or failed.
        """
        lock_acquired = (
            await self.repository.try_acquire_idempotency_lock(
                idempotency_key
            )
        )
        if lock_acquired:
            return None  # Lock acquired — caller proceeds

        # Lock not acquired — check if result is ready
        cached_record = await self.repository.get_idempotency_record(
            idempotency_key
        )
        if cached_record:
            status_code = cached_record["response_status"]
            body = cached_record["response_body"]
            if status_code == 400:
                raise DailyLimitExceededException(
                    message=body.get(
                        "message", "Limite diário excedido"
                    )
                )
            elif status_code == "PROCESSING":
                raise DailyLimitExceededException(
                    message="Transação em processamento"
                )
            return TransferResponse(**body)

        # No record found — still processing
        raise DailyLimitExceededException(
            message="Transação em processamento"
        )

    async def save_success(
        self,
        idempotency_key: str,
        response: TransferResponse,
    ) -> None:
        """Step 5 (success): Persist idempotency record with 201."""
        await self.repository.save_idempotency_record(
            idempotency_key=idempotency_key,
            response_status=201,
            response_body=response.model_dump(),
        )

    async def save_failure(
        self,
        idempotency_key: str,
        error: DailyLimitExceededException,
    ) -> None:
        """Step 5 (failure): Persist idempotency record with 400."""
        await self.repository.save_idempotency_record(
            idempotency_key=idempotency_key,
            response_status=400,
            response_body={
                "error_code": error.error_code,
                "message": error.message,
            },
        )
