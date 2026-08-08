from unittest.mock import AsyncMock

import pytest

from src.exceptions import DailyLimitExceededException
from src.models.pix import PixKeyType, TransferResponse, TransferStatus
from src.repository.interface import IPixRepository
from src.services.idempotency_service import IdempotencyService


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock(spec=IPixRepository)


@pytest.mark.asyncio
async def test_get_cached_response_returns_none_on_cache_miss(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.get_idempotency_record.return_value = None
    service = IdempotencyService(repository=mock_repository)

    res = await service.get_cached_response("key-123")
    assert res is None


@pytest.mark.asyncio
async def test_get_cached_response_returns_transfer_response_on_201(
    mock_repository: AsyncMock,
) -> None:
    cached_body = {
        "transfer_id": "tx-123",
        "account_id": "acc-01",
        "amount": 100.0,
        "pix_key": "user@example.com",
        "pix_key_type": "EMAIL",
        "status": "APPROVED",
        "created_at": "2026-08-08T00:00:00Z",
    }
    mock_repository.get_idempotency_record.return_value = {
        "response_status": 201,
        "response_body": cached_body,
    }
    service = IdempotencyService(repository=mock_repository)

    res = await service.get_cached_response("key-123")
    assert isinstance(res, TransferResponse)
    assert res.transfer_id == "tx-123"
    assert res.status == TransferStatus.APPROVED


@pytest.mark.asyncio
async def test_get_cached_response_raises_exception_on_400(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.get_idempotency_record.return_value = {
        "response_status": 400,
        "response_body": {"message": "Limite diário excedido"},
    }
    service = IdempotencyService(repository=mock_repository)

    with pytest.raises(DailyLimitExceededException, match="Limite diário excedido"):
        await service.get_cached_response("key-123")


@pytest.mark.asyncio
async def test_acquire_lock_returns_none_when_lock_acquired(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.try_acquire_idempotency_lock.return_value = True
    service = IdempotencyService(repository=mock_repository)

    res = await service.acquire_lock("key-123")
    assert res is None


@pytest.mark.asyncio
async def test_acquire_lock_returns_cached_response_when_lock_failed_and_record_ready(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.try_acquire_idempotency_lock.return_value = False
    cached_body = {
        "transfer_id": "tx-123",
        "account_id": "acc-01",
        "amount": 100.0,
        "pix_key": "user@example.com",
        "pix_key_type": "EMAIL",
        "status": "APPROVED",
        "created_at": "2026-08-08T00:00:00Z",
    }
    mock_repository.get_idempotency_record.return_value = {
        "response_status": 201,
        "response_body": cached_body,
    }
    service = IdempotencyService(repository=mock_repository)

    res = await service.acquire_lock("key-123")
    assert isinstance(res, TransferResponse)
    assert res.transfer_id == "tx-123"


@pytest.mark.asyncio
async def test_acquire_lock_raises_when_processing(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.try_acquire_idempotency_lock.return_value = False
    mock_repository.get_idempotency_record.return_value = {
        "response_status": "PROCESSING",
        "response_body": {},
    }
    service = IdempotencyService(repository=mock_repository)

    with pytest.raises(DailyLimitExceededException, match="Transação em processamento"):
        await service.acquire_lock("key-123")


@pytest.mark.asyncio
async def test_save_success_calls_repository(
    mock_repository: AsyncMock,
) -> None:
    service = IdempotencyService(repository=mock_repository)
    response = TransferResponse(
        transfer_id="tx-123",
        account_id="acc-01",
        amount=100.0,
        pix_key="user@example.com",
        pix_key_type=PixKeyType.EMAIL,
        status=TransferStatus.APPROVED,
        created_at="2026-08-08T00:00:00Z",
    )

    await service.save_success("key-123", response)
    mock_repository.save_idempotency_record.assert_called_once_with(
        idempotency_key="key-123",
        response_status=201,
        response_body=response.model_dump(),
    )


@pytest.mark.asyncio
async def test_save_failure_calls_repository(
    mock_repository: AsyncMock,
) -> None:
    service = IdempotencyService(repository=mock_repository)
    error = DailyLimitExceededException()

    await service.save_failure("key-123", error)
    mock_repository.save_idempotency_record.assert_called_once_with(
        idempotency_key="key-123",
        response_status=400,
        response_body={
            "error_code": "DAILY_LIMIT_EXCEEDED",
            "message": "Limite diário excedido",
        },
    )
