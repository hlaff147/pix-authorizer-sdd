import uuid
from datetime import datetime, timezone
from typing import Optional

from src.config import settings
from src.exceptions import DailyLimitExceededException
from src.models.pix import (
    TransferRequest,
    TransferResponse,
    TransferStatus,
)
from src.repository.interface import IPixRepository


class PixService:
    def __init__(self, repository: IPixRepository) -> None:
        self.repository = repository

    async def process_transfer(
        self, request: TransferRequest, idempotency_key: str
    ) -> TransferResponse:
        # 1. Checagem de idempotência — retorno do cache se já processado
        cached_record = await self.repository.get_idempotency_record(
            idempotency_key
        )
        if cached_record:
            status_code = cached_record["response_status"]
            body = cached_record["response_body"]
            if status_code == 400:
                raise DailyLimitExceededException(
                    message=body.get("message", "Limite diário excedido")
                )
            return TransferResponse(**body)

        # 2. Lock atômico de idempotência (previne race condition)
        lock_acquired = await self.repository.try_acquire_idempotency_lock(
            idempotency_key
        )
        if not lock_acquired:
            # Outra requisição está processando ou já processou — espera e consulta resultado
            cached_record = await self.repository.get_idempotency_record(
                idempotency_key
            )
            if cached_record:
                status_code = cached_record["response_status"]
                body = cached_record["response_body"]
                if status_code == 400:
                    raise DailyLimitExceededException(
                        message=body.get("message", "Limite diário excedido")
                    )
                elif status_code == "PROCESSING":
                    raise DailyLimitExceededException(
                        message="Transação em processamento"
                    )
                return TransferResponse(**body)
            # Se ainda está processando, trata como conflito
            raise DailyLimitExceededException(
                message="Transação em processamento"
            )

        now_utc = datetime.now(timezone.utc)
        created_at_str = now_utc.isoformat()
        date_str = now_utc.strftime("%Y-%m-%d")
        transfer_id = str(uuid.uuid4())

        # 3. Validação e reserva de limite diário
        approved = await self.repository.try_reserve_daily_limit(
            account_id=request.account_id,
            date_str=date_str,
            amount=request.amount,
            updated_at=created_at_str,
            max_daily_limit=settings.max_daily_limit,
        )

        status = (
            TransferStatus.APPROVED if approved else TransferStatus.REJECTED
        )

        response = TransferResponse(
            transfer_id=transfer_id,
            account_id=request.account_id,
            amount=request.amount,
            pix_key=request.pix_key,
            pix_key_type=request.pix_key_type,
            status=status,
            created_at=created_at_str,
        )

        # 4. Persistência imutável (auditoria)
        await self.repository.save_transaction(response)

        if not approved:
            error = DailyLimitExceededException()
            await self.repository.save_idempotency_record(
                idempotency_key=idempotency_key,
                response_status=400,
                response_body={
                    "error_code": error.error_code,
                    "message": error.message,
                },
            )
            raise error

        # 5. Sucesso
        await self.repository.save_idempotency_record(
            idempotency_key=idempotency_key,
            response_status=201,
            response_body=response.model_dump(),
        )

        return response
