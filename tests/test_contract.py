import uuid
import pytest
import schemathesis
from fastapi.testclient import TestClient

from src.main import app

# Instância do Schemathesis configurada a partir do contrato specs/openapi.yaml
schema = schemathesis.openapi.from_path("specs/openapi.yaml", app=app)
client = TestClient(app)


@schema.parametrize()
def test_schemathesis_contract(case: schemathesis.Case) -> None:
    """Valida se todas as rotas e casos de teste gerados respeitam o contrato OpenAPI."""
    response = case.call_asgi()
    case.validate_response(response)


def test_approved_transfer_success() -> None:
    """Garante que uma transferência PIX válida dentro dos limites é aprovada com status 201."""
    idempotency_key = str(uuid.uuid4())
    payload = {
        "account_id": f"acc-{uuid.uuid4().hex[:6]}",
        "amount": 1500.00,
        "pix_key": "user@example.com",
        "pix_key_type": "EMAIL",
    }
    headers = {"X-Idempotency-Key": idempotency_key}

    response = client.post("/v1/transfers", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["amount"] == 1500.00
    assert data["account_id"] == payload["account_id"]
    assert "transfer_id" in data
    assert "created_at" in data


def test_reject_single_transfer_limit_exceeded() -> None:
    """Garante que transferência individual acima de R$ 5.000,00 é rejeitada com status 422 (RN-001)."""
    idempotency_key = str(uuid.uuid4())
    payload = {
        "account_id": f"acc-{uuid.uuid4().hex[:6]}",
        "amount": 5000.01,
        "pix_key": "12345678900",
        "pix_key_type": "CPF",
    }
    headers = {"X-Idempotency-Key": idempotency_key}

    response = client.post("/v1/transfers", json=payload, headers=headers)
    assert response.status_code == 422


def test_reject_daily_limit_exceeded() -> None:
    """Garante que o somatório diário acima de R$ 20.000,00 resulta em 400 Bad Request (RN-002)."""
    account_id = f"acc-limit-{uuid.uuid4().hex[:6]}"
    payload_1 = {
        "account_id": account_id,
        "amount": 5000.00,
        "pix_key": "user@example.com",
        "pix_key_type": "EMAIL",
    }

    # Executa 4 transações de R$ 5.000,00 (Total = R$ 20.000,00)
    for _ in range(4):
        headers = {"X-Idempotency-Key": str(uuid.uuid4())}
        resp = client.post("/v1/transfers", json=payload_1, headers=headers)
        assert resp.status_code == 201

    # A 5ª transação excede o limite diário de R$ 20.000,00
    payload_2 = {
        "account_id": account_id,
        "amount": 100.00,
        "pix_key": "user@example.com",
        "pix_key_type": "EMAIL",
    }
    headers_5 = {"X-Idempotency-Key": str(uuid.uuid4())}
    resp_5 = client.post("/v1/transfers", json=payload_2, headers=headers_5)
    assert resp_5.status_code == 400
    data = resp_5.json()
    assert data["error_code"] == "DAILY_LIMIT_EXCEEDED"
    assert data["message"] == "Limite diário excedido"


def test_idempotency_returns_cached_response() -> None:
    """Garante que requisições duplicadas com a mesma X-Idempotency-Key retornam exatamente o mesmo payload (RN-003)."""
    idempotency_key = str(uuid.uuid4())
    payload = {
        "account_id": f"acc-idem-{uuid.uuid4().hex[:6]}",
        "amount": 1000.00,
        "pix_key": "+5511999999999",
        "pix_key_type": "PHONE",
    }
    headers = {"X-Idempotency-Key": idempotency_key}

    first_resp = client.post("/v1/transfers", json=payload, headers=headers)
    assert first_resp.status_code == 201
    first_data = first_resp.json()

    second_resp = client.post("/v1/transfers", json=payload, headers=headers)
    assert second_resp.status_code == 201
    second_data = second_resp.json()

    assert first_data == second_data


def test_missing_idempotency_key_header() -> None:
    """Garante que a ausência do header X-Idempotency-Key retorna erro 422 de schema."""
    payload = {
        "account_id": "acc-no-header",
        "amount": 100.00,
        "pix_key": "key@test.com",
        "pix_key_type": "EMAIL",
    }
    response = client.post("/v1/transfers", json=payload)
    assert response.status_code == 422
