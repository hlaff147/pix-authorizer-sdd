from src.config import settings
from src.models.pix import TransferStatus
from src.repository.interface import IPixRepository


class DailyLimitService:
    """Handles daily transfer limit validation and atomic reservation."""

    def __init__(self, repository: IPixRepository) -> None:
        self.repository = repository

    async def try_reserve(
        self,
        account_id: str,
        date_str: str,
        amount: float,
        updated_at: str,
    ) -> TransferStatus:
        """Step 3: Try to reserve the amount against the daily limit.

        Returns APPROVED if reserved, REJECTED if limit exceeded.
        """
        approved = await self.repository.try_reserve_daily_limit(
            account_id=account_id,
            date_str=date_str,
            amount=amount,
            updated_at=updated_at,
            max_daily_limit=settings.max_daily_limit,
        )
        return (
            TransferStatus.APPROVED
            if approved
            else TransferStatus.REJECTED
        )
