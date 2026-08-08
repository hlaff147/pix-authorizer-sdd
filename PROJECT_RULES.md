# Project Rules & Coding Standards: pix-authorizer-sdd

## 1. Language & Localization Policy

### 1.1 General Rule

* **Strict English Policy:** All code, variable names, function names, class names, file names, inline comments, docstrings (except test descriptions), commits, and technical documentation must be written in **English**.

### 1.2 Allowed Exceptions (PT-BR)

* **`README.md`:** Written in **Portuguese (PT-BR)** to facilitate project presentation, architecture overview, and onboarding for Brazilian teams.
* **Test Case Descriptions:** Test docstrings and scenario explanations inside `tests/` may be written in **Portuguese (PT-BR)** to clearly express business rules and requirements being validated.
  * *Example:*

    ```python
    def test_reject_transaction_above_single_limit():
        """Garante que transações individuais superiores a R$ 5.000,00 sejam rejeitadas com erro 422."""
        ...
    ```

---

## 2. Spec-Driven Development (SDD) Guidelines

1. **Single Source of Truth:** `specs/openapi.yaml` is the contract of truth.
2. **Contract First:** No implementation or model creation is allowed before the `openapi.yaml` file is updated and validated.
3. **Strict Schema Parity:** Pydantic models in `src/models/` must match `specs/openapi.yaml` field types, constraints, enums, and validation messages exactly.
4. **Contract Verification:** All pull requests must pass contract validation tests powered by `Schemathesis`.

---

## 3. Python & Code Style Standards

### 3.1 Syntax & Tooling

* **Python Version:** 3.12+
* **Type Hinting:** Mandatory for all function arguments, return types, and class attributes.
* **Code Formatting:** `ruff` or `black` with a maximum line length of **100 characters**.
* **Linter:** `ruff` for linting and import sorting (`isort` style).

### 3.2 Naming Conventions

* **Files & Directories:** `snake_case` (e.g., `pix_service.py`, `dynamodb_repository.py`).
* **Classes:** `PascalCase` (e.g., `TransferRequest`, `PixRepository`).
* **Functions & Variables:** `snake_case` (e.g., `process_transfer`, `daily_spent`).
* **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_DAILY_LIMIT`, `TABLE_NAME`).

### 3.3 Asynchronous Execution

* Use `async`/`await` for I/O-bound operations (FastAPI endpoints, DynamoDB calls via `aioboto3`).

---

## 4. Architecture & AWS Constraints

### 4.1 Serverless Abstraction

* **FastAPI Entrypoint:** Exposed via `Mangum` ASGI adapter inside `src/main.py` (`handler = Mangum(app)`).
* **AWS SDK:** Use `boto3` or `aioboto3` initialized with dynamic endpoint configurations to support LocalStack seamlessly.

### 4.2 DynamoDB Single-Table Design Rules

* Partition Key (`PK`) and Sort Key (`SK`) must strictly follow predefined string patterns:
  * **Daily Limit:** `PK = "ACCOUNT#<account_id>"`, `SK = "LIMIT#<YYYY-MM-DD>"`
  * **Transaction:** `PK = "ACCOUNT#<account_id>"`, `SK = "TX#<transfer_id>"`
  * **Idempotency:** `PK = "IDEMPOTENCY#<uuid>"`, `SK = "LOCK"`
* Never perform full table scans. All queries must target explicit `PK` or `PK` + `SK` prefixes.

### 4.3 Environment & Configuration

* Do not hardcode secret keys, region names, or endpoint URLs.
* All configuration must be loaded from environment variables using `pydantic-settings`.

---

## 5. Testing & Quality Assurance

1. **Contract Testing:** `Schemathesis` tests must run against the running FastAPI/LocalStack instance to verify OpenAPI compliance.
2. **Unit & Integration Tests:** Written using `pytest` and `pytest-asyncio`.
3. **Isolation:** Tests must clean up created DynamoDB items or use isolated account/idempotency keys per test execution.

---

## 6. Git & Commit Messages

Follow the **Conventional Commits** specification in **English**:

* `feat: add idempotency key check in dynamodb`
* `fix: correct validation status code for invalid pix keys`
* `docs: update Portuguese README with localstack instructions`
* `test: add test scenario for daily limit breach`
* `refactor: optimize dynamodb single-table key generator`
