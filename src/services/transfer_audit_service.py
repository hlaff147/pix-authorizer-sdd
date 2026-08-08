import uuid

from src.models.pix import (
    TransferRequest,
    TransferResponse,
    TransferStatus,
)
from src.repository.interface import IPixRepository


class TransferAuditService:
    """Handles transfer response creation and audit persistence."""

    def __init__(self, repository: IPixRepository) -> None:
        self.repository = repository

    def build_response(
        self,
        request: TransferRequest,
        status: TransferStatus,
        created_at: str,
    ) -> TransferResponse:
        """Build a TransferResponse with a new UUID."""
        return TransferResponse(
            transfer_id=str(uuid.uuid4()),
            account_id=request.account_id,
            amount=request.amount,
            pix_key=request.pix_key,
            pix_key_type=request.pix_key_type,
            status=status,
            created_at=created_at,
        )

    async def save(self, response: TransferResponse) -> None:
        """Step 4: Persist the transaction for audit trail."""
        await self.repository.save_transaction(response)
