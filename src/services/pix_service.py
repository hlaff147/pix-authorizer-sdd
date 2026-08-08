import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.config import settings
from src.models.pix import (
    ErrorResponse,
    TransferRequest,
    TransferResponse,
    TransferStatus,
)
from src.repository.dynamodb import PixRepository


class PixService:
    def __init__(self, repository: Optional[PixRepository] = None) -> None:
        self.repository = repository or PixRepository()

    async def process_transfer(
        self, request: TransferRequest, idempotency_key: str
    ) -> Tuple[Dict[str, Any], int]:
        # 1. Check idempotency
        cached_record = await self.repository.get_idempotency_record(idempotency_key)
        if cached_record:
            return cached_record["response_body"], cached_record["response_status"]

        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")
        created_at_str = now_utc.isoformat()
        transfer_id = str(uuid.uuid4())

        # 2. Check and reserve daily limit
        approved = await self.repository.try_reserve_daily_limit(
            account_id=request.account_id,
            date_str=date_str,
            amount=request.amount,
            updated_at=created_at_str,
            max_daily_limit=settings.max_daily_limit,
        )

        if not approved:
            # Save rejected transaction for audit
            await self.repository.save_transaction(
                account_id=request.account_id,
                transfer_id=transfer_id,
                amount=request.amount,
                pix_key=request.pix_key,
                pix_key_type=request.pix_key_type.value,
                status=TransferStatus.REJECTED.value,
                created_at=created_at_str,
            )

            error_payload = ErrorResponse(
                error_code="DAILY_LIMIT_EXCEEDED",
                message="Limite diário excedido",
            ).model_dump()

            await self.repository.save_idempotency_record(
                idempotency_key=idempotency_key,
                response_status=400,
                response_body=error_payload,
            )
            return error_payload, 400

        # 3. Transaction Approved
        response_obj = TransferResponse(
            transfer_id=transfer_id,
            account_id=request.account_id,
            amount=request.amount,
            pix_key=request.pix_key,
            pix_key_type=request.pix_key_type,
            status=TransferStatus.APPROVED,
            created_at=created_at_str,
        )
        response_payload = response_obj.model_dump()

        await self.repository.save_transaction(
            account_id=request.account_id,
            transfer_id=transfer_id,
            amount=request.amount,
            pix_key=request.pix_key,
            pix_key_type=request.pix_key_type.value,
            status=TransferStatus.APPROVED.value,
            created_at=created_at_str,
        )

        await self.repository.save_idempotency_record(
            idempotency_key=idempotency_key,
            response_status=201,
            response_body=response_payload,
        )

        return response_payload, 201
