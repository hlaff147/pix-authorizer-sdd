from unittest.mock import AsyncMock

import pytest

from src.models.pix import TransferStatus
from src.repository.interface import IPixRepository
from src.services.daily_limit_service import DailyLimitService


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock(spec=IPixRepository)


@pytest.mark.asyncio
async def test_try_reserve_returns_approved_when_limit_reserved(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.try_reserve_daily_limit.return_value = True
    service = DailyLimitService(repository=mock_repository)

    status = await service.try_reserve(
        account_id="acc-01",
        date_str="2026-08-08",
        amount=100.0,
        updated_at="2026-08-08T00:00:00Z",
    )

    assert status == TransferStatus.APPROVED


@pytest.mark.asyncio
async def test_try_reserve_returns_rejected_when_limit_exceeded(
    mock_repository: AsyncMock,
) -> None:
    mock_repository.try_reserve_daily_limit.return_value = False
    service = DailyLimitService(repository=mock_repository)

    status = await service.try_reserve(
        account_id="acc-01",
        date_str="2026-08-08",
        amount=10000.0,
        updated_at="2026-08-08T00:00:00Z",
    )

    assert status == TransferStatus.REJECTED
