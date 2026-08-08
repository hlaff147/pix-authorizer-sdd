from typing import Any, Dict, Optional, Protocol

from src.models.pix import TransferResponse


class IPixRepository(Protocol):
    """Contrato abstrato para a camada de persistência."""

    async def get_idempotency_record(
        self, idempotency_key: str
    ) -> Optional[Dict[str, Any]]: ...

    async def try_acquire_idempotency_lock(
        self,
        idempotency_key: str,
        ttl_seconds: int = 86400,
    ) -> bool: ...

    async def try_reserve_daily_limit(
        self,
        account_id: str,
        date_str: str,
        amount: float,
        updated_at: str,
        max_daily_limit: float,
    ) -> bool: ...

    async def save_transaction(self, response: TransferResponse) -> None: ...

    async def save_idempotency_record(
        self,
        idempotency_key: str,
        response_status: int,
        response_body: Dict[str, Any],
    ) -> None: ...
