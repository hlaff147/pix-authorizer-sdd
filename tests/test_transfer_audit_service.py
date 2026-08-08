from unittest.mock import AsyncMock

import pytest

from src.models.pix import PixKeyType, TransferRequest, TransferResponse, TransferStatus
from src.repository.interface import IPixRepository
from src.services.transfer_audit_service import TransferAuditService


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock(spec=IPixRepository)


def test_build_response_creates_valid_transfer_response(
    mock_repository: AsyncMock,
) -> None:
    service = TransferAuditService(repository=mock_repository)
    req = TransferRequest(
        account_id="acc-01",
        amount=150.0,
        pix_key="user@example.com",
        pix_key_type=PixKeyType.EMAIL,
    )
    created_at = "2026-08-08T00:00:00Z"

    resp = service.build_response(req, TransferStatus.APPROVED, created_at)

    assert isinstance(resp, TransferResponse)
    assert resp.account_id == "acc-01"
    assert resp.amount == 150.0
    assert resp.pix_key == "user@example.com"
    assert resp.pix_key_type == PixKeyType.EMAIL
    assert resp.status == TransferStatus.APPROVED
    assert resp.created_at == created_at
    assert resp.transfer_id is not None


@pytest.mark.asyncio
async def test_save_calls_repository_save_transaction(
    mock_repository: AsyncMock,
) -> None:
    service = TransferAuditService(repository=mock_repository)
    response = TransferResponse(
        transfer_id="tx-123",
        account_id="acc-01",
        amount=100.0,
        pix_key="user@example.com",
        pix_key_type=PixKeyType.EMAIL,
        status=TransferStatus.APPROVED,
        created_at="2026-08-08T00:00:00Z",
    )

    await service.save(response)
    mock_repository.save_transaction.assert_called_once_with(response)
