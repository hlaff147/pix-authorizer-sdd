# Technical Design Document (TDD) - Pix Authorizer Service

## 1. Visão Geral da Arquitetura

O **Pix Authorizer Service** é um microsserviço serverless construído com a abordagem **Spec-Driven Development (SDD)**. Ele provê autorização de baixo tempo de resposta para transações PIX, aplicando regras de idempotência e validações estritas de contrato antes da persistência.

+---------------------------+
|   Cliente / Schemathesis  |
+-------------+-------------+
| (HTTP POST /v1/transfers com X-Idempotency-Key)
v
+---------------------------+
|  AWS API Gateway (Local)  |
+-------------+-------------+
|
v
+---------------------------+
|   AWS Lambda (Python 3.12)|
+---------------------------+
|  - Mangum (ASGI Adapter)  |
|  - FastAPI (Framework)    |
|  - Pydantic v2 (Validation)|
+-------------+-------------+
|
v
+---------------------------+
|  AWS DynamoDB (Local)     |
|  (Single-Table Design)    |
+---------------------------+

---

## 2. Stack Tecnológica

* **Linguagem:** Python 3.12
* **Web Framework:** FastAPI + Mangum (para compatibilidade com AWS Lambda)
* **Validação de Dados:** Pydantic v2
* **Banco de Dados:** AWS DynamoDB (LocalStack)
* **Containerização:** Docker & Docker Compose
* **Infraestrutura Local:** LocalStack (Simulação de API Gateway, Lambda, DynamoDB)
* **Testes de Contrato:** Schemathesis (Property-based Contract Testing)

---

## 3. Modelagem de Dados — Single-Table Design (DynamoDB)

Tabela: `pix_transactions_store`
Chaves Primárias: `PK` (String), `SK` (String)

| Entidade / Caso de Uso | PK | SK | Atributos Secundários |
| :--- | :--- | :--- | :--- |
| **Controle de Limite Diário** | `ACCOUNT#<account_id>` | `LIMIT#<YYYY-MM-DD>` | `daily_spent` (Decimal), `updated_at` (ISO8601) |
| **Registro de Transação** | `ACCOUNT#<account_id>` | `TX#<transfer_id>` | `amount` (Decimal), `pix_key` (String), `status` (APPROVED/REJECTED), `created_at` |
| **Chave de Idempotência** | `IDEMPOTENCY#<uuid>` | `LOCK` | `response_status` (Int), `response_body` (JSON), `ttl` (Timestamp) |

---

## 4. Pipeline de Qualidade e SDD (Spec-Driven Development)

1. **Especificação Inegociável:** O arquivo `specs/openapi.yaml` atua como o único contrato válido da aplicação.
2. **Derivação de Tipos:** Modelos Pydantic v2 replicam fielmente os schemas e validações declarados no OpenAPI.
3. **Property-Based Testing:** O framework `Schemathesis` realiza fuzzing de dados contra a aplicação no ambiente LocalStack, garantindo que respostas da API (sucessos e erros 422/400) sigam 100% a especificação.
