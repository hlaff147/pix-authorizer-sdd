import json
import time
from decimal import Decimal
from typing import Any, Dict, Optional

import aioboto3
from botocore.exceptions import ClientError

from src.config import settings


class PixRepository:
    def __init__(self) -> None:
        self.session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def _get_resource_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if settings.dynamodb_endpoint_url:
            kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        return kwargs

    async def get_idempotency_record(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        pk = f"IDEMPOTENCY#{idempotency_key}"
        sk = "LOCK"

        async with self.session.resource("dynamodb", **self._get_resource_kwargs()) as dynamo:
            table = await dynamo.Table(settings.dynamodb_table_name)
            response = await table.get_item(Key={"PK": pk, "SK": sk})
            item = response.get("Item")
            if item:
                body = item["response_body"]
                if isinstance(body, str):
                    body = json.loads(body)
                return {
                    "response_status": int(item["response_status"]),
                    "response_body": body,
                }
            return None

    async def save_idempotency_record(
        self,
        idempotency_key: str,
        response_status: int,
        response_body: Dict[str, Any],
        ttl_seconds: int = 86400,
    ) -> None:
        pk = f"IDEMPOTENCY#{idempotency_key}"
        sk = "LOCK"
        ttl = int(time.time()) + ttl_seconds

        async with self.session.resource("dynamodb", **self._get_resource_kwargs()) as dynamo:
            table = await dynamo.Table(settings.dynamodb_table_name)
            await table.put_item(
                Item={
                    "PK": pk,
                    "SK": sk,
                    "response_status": response_status,
                    "response_body": json.dumps(response_body),
                    "ttl": ttl,
                }
            )

    async def get_daily_spent(self, account_id: str, date_str: str) -> float:
        pk = f"ACCOUNT#{account_id}"
        sk = f"LIMIT#{date_str}"

        async with self.session.resource("dynamodb", **self._get_resource_kwargs()) as dynamo:
            table = await dynamo.Table(settings.dynamodb_table_name)
            response = await table.get_item(Key={"PK": pk, "SK": sk})
            item = response.get("Item")
            if item and "daily_spent" in item:
                return float(item["daily_spent"])
            return 0.0

    async def try_reserve_daily_limit(
        self,
        account_id: str,
        date_str: str,
        amount: float,
        updated_at: str,
        max_daily_limit: float = 20000.00,
        max_retries: int = 3,
    ) -> bool:
        pk = f"ACCOUNT#{account_id}"
        sk = f"LIMIT#{date_str}"
        dec_amount = Decimal(f"{amount:.2f}")
        dec_max_limit = Decimal(f"{max_daily_limit:.2f}")

        async with self.session.resource("dynamodb", **self._get_resource_kwargs()) as dynamo:
            table = await dynamo.Table(settings.dynamodb_table_name)

            for _ in range(max_retries):
                response = await table.get_item(Key={"PK": pk, "SK": sk})
                item = response.get("Item")

                if item and "daily_spent" in item:
                    current_spent = Decimal(str(item["daily_spent"]))
                    if current_spent + dec_amount > dec_max_limit:
                        return False

                    condition_expr = "daily_spent = :current_spent"
                    expr_attr_values = {
                        ":amount": dec_amount,
                        ":current_spent": current_spent,
                        ":now": updated_at,
                    }
                else:
                    if dec_amount > dec_max_limit:
                        return False

                    condition_expr = "attribute_not_exists(daily_spent)"
                    expr_attr_values = {
                        ":amount": dec_amount,
                        ":now": updated_at,
                    }

                try:
                    await table.update_item(
                        Key={"PK": pk, "SK": sk},
                        UpdateExpression="SET daily_spent = if_not_exists(daily_spent, :zero) + :amount, updated_at = :now",
                        ConditionExpression=condition_expr,
                        ExpressionAttributeValues={
                            ":zero": Decimal("0.00"),
                            **expr_attr_values,
                        },
                    )
                    return True
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                        continue
                    raise e

            return False

    async def save_transaction(
        self,
        account_id: str,
        transfer_id: str,
        amount: float,
        pix_key: str,
        pix_key_type: str,
        status: str,
        created_at: str,
    ) -> None:
        pk = f"ACCOUNT#{account_id}"
        sk = f"TX#{transfer_id}"

        async with self.session.resource("dynamodb", **self._get_resource_kwargs()) as dynamo:
            table = await dynamo.Table(settings.dynamodb_table_name)
            await table.put_item(
                Item={
                    "PK": pk,
                    "SK": sk,
                    "transfer_id": transfer_id,
                    "account_id": account_id,
                    "amount": Decimal(f"{amount:.2f}"),
                    "pix_key": pix_key,
                    "pix_key_type": pix_key_type,
                    "status": status,
                    "created_at": created_at,
                }
            )
