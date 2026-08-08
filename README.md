# 🏦 Pix Authorizer SDD

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI Version" />
  <img src="https://img.shields.io/badge/DynamoDB-Single--Table-FF9900?logo=amazondynamodb" alt="DynamoDB Single-Table" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
</p>

O **Pix Authorizer Service** é um microsserviço de alta performance construído seguindo a abordagem **Spec-Driven Development (SDD)** (Desenvolvimento Orientado a Especificação). Ele atua como um gateway de autorização rápida para transações PIX, validando contratos OpenAPI, aplicando regras de idempotência estrita e controlando limites operacionais diários de forma atômica antes que as transações atinjam os sistemas legados de liquidação bancária.

---

## 1. Regras de Negócio (Business Rules)

| ID | Regra de Negócio | Ação em caso de violação | Código HTTP |
| :--- | :--- | :--- | :--- |
| **RN-001** | **Limite por Transação:** O valor individual da transferência não pode exceder **R$ 5.000,00**. | Rejeição imediata por validação de contrato. | `422 Unprocessable Entity` |
| **RN-002** | **Limite Acumulado Diário:** O somatório das transações aprovadas de uma conta no mesmo dia civil não pode ultrapassar **R$ 20.000,00**. | Recusa da transação com mensagem de limite excedido. | `400 Bad Request` |
| **RN-003** | **Idempotência Estrita:** Toda requisição exige o cabeçalho HTTP `X-Idempotency-Key` (UUIDv4). Chaves repetidas retornam exatamente a mesma resposta original. | Retorno da resposta em cache, sem novo débito ou processamento. | Mesmo status original |
| **RN-004** | **Validação de Chave PIX:** A chave receptora deve pertencer a uma das categorias válidas: `CPF`, `CNPJ`, `EMAIL`, `PHONE` (E.164) ou `EVP` (aleatória). | Rejeição por validação de contrato. | `422 Unprocessable Entity` |

---

## 2. Arquitetura de Alto Nível

O fluxo completo, desde a chamada do cliente HTTP (ou a suíte de testes do Schemathesis) até a persistência no banco de dados, é mapeado a seguir:

```mermaid
graph TB
    subgraph Cliente
        A["🧑‍💻 Cliente HTTP<br/><i>curl / Postman / Schemathesis</i>"]
    end

    subgraph AWS["☁️ AWS Cloud (Simulado via LocalStack)"]
        B["🌐 API Gateway"]
        subgraph Lambda["⚡ AWS Lambda"]
            C["Mangum<br/><i>ASGI Adapter</i>"]
            D["FastAPI<br/><i>Roteamento + Validação</i>"]
            E["Pydantic v2<br/><i>Schema Validation</i>"]
            F["PixService<br/><i>Regras de Negócio</i>"]
            G["PixRepository<br/><i>Persistência Async</i>"]
        end
        H["🗄️ DynamoDB<br/><i>Single-Table Design</i>"]
    end

    A -- "POST /v1/transfers<br/>+ X-Idempotency-Key" --> B
    B --> C --> D --> E --> F --> G
    G -- "aioboto3 (async)" --> H

    style A fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    style B fill:#f59e0b,stroke:#d97706,color:#1e293b
    style H fill:#ff9900,stroke:#cc7a00,color:#1e293b
```

---

## 3. Fluxo de Execução da Transação

A lógica interna da API executa validações em camadas (contrato, idempotência, limites operacionais e concorrência) de forma coordenada:

```mermaid
sequenceDiagram
    participant C as 🧑‍💻 Cliente
    participant F as FastAPI
    participant S as PixService
    participant R as PixRepository
    participant D as DynamoDB

    C->>F: POST /v1/transfers<br/>(X-Idempotency-Key)
    F->>F: Validação Pydantic (RN-001 + RN-004)

    alt ❌ Falha na validação
        F-->>C: 422 Unprocessable Entity
    end

    F->>S: process_transfer(request, key)
    S->>R: get_idempotency_record(key)
    R->>D: GetItem (IDEMPOTENCY#key / LOCK)
    D-->>R: Item ou vazio

    alt 🔄 Chave já existe (replay)
        R-->>S: resposta cacheada
        S-->>F: payload + status original
        F-->>C: Resposta idempotente
    end

    S->>R: try_reserve_daily_limit(account, amount)
    R->>D: GetItem + UpdateItem com ConditionExpression
    D-->>R: sucesso ou ConditionalCheckFailed

    alt ❌ Limite diário excedido (RN-002)
        R-->>S: false
        S->>R: save_transaction(REJECTED)
        S->>R: save_idempotency(400, error)
        S-->>F: ErrorResponse
        F-->>C: 400 Bad Request
    end

    S->>R: save_transaction(APPROVED)
    R->>D: PutItem (ACCOUNT#id / TX#uuid)
    S->>R: save_idempotency(201, response)
    R->>D: PutItem (IDEMPOTENCY#key / LOCK)
    S-->>F: TransferResponse
    F-->>C: 201 Created
```

---

## 4. Modelagem de Dados: Single-Table Design

Para otimizar o tempo de resposta e garantir consistência na simulação serverless com o AWS DynamoDB, o projeto utiliza a estratégia de **Tabela Única (Single-Table Design)**:

```mermaid
erDiagram
    PIX_TRANSACTIONS_STORE {
        string PK PK "Partition Key"
        string SK SK "Sort Key"
    }

    LIMITE_DIARIO {
        string PK PK "ACCOUNT#account_id"
        string SK SK "LIMIT#YYYY-MM-DD"
        decimal daily_spent "Acumulado do dia"
        string updated_at "ISO 8601"
    }

    TRANSACAO {
        string PK PK "ACCOUNT#account_id"
        string SK SK "TX#transfer_id"
        decimal amount "Valor da transferência"
        string pix_key "Chave PIX destino"
        string pix_key_type "CPF CNPJ EMAIL PHONE EVP"
        string status "APPROVED ou REJECTED"
        string created_at "ISO 8601"
    }

    IDEMPOTENCIA {
        string PK PK "IDEMPOTENCY#uuid"
        string SK SK "LOCK"
        int response_status "HTTP status code"
        string response_body "JSON serializado"
        int ttl "Unix timestamp"
    }

    PIX_TRANSACTIONS_STORE ||--o{ LIMITE_DIARIO : "entidade"
    PIX_TRANSACTIONS_STORE ||--o{ TRANSACAO : "entidade"
    PIX_TRANSACTIONS_STORE ||--o{ IDEMPOTENCIA : "entidade"
```

---

## 5. Pipeline Spec-Driven Development (SDD)

O contrato OpenAPI atua como a única fonte da verdade. O ciclo abaixo ilustra como as modificações fluem da especificação para a validação final da API:

```mermaid
flowchart LR
    A["📝 specs/openapi.yaml<br/><i>Contrato OpenAPI 3.0</i>"] --> B["🔧 src/models/pix.py<br/><i>Pydantic v2 Schemas</i>"]
    B --> C["⚙️ src/services/<br/><i>Regras de Negócio</i>"]
    C --> D["🚀 src/main.py<br/><i>FastAPI Endpoints</i>"]
    D --> E["🧪 tests/test_contract.py<br/><i>Schemathesis Fuzzing</i>"]
    E -->|"Valida contra"| A

    style A fill:#4f46e5,stroke:#3730a3,color:#fff
    style B fill:#7c3aed,stroke:#5b21b6,color:#fff
    style C fill:#9333ea,stroke:#7e22ce,color:#fff
    style D fill:#a855f7,stroke:#9333ea,color:#fff
    style E fill:#c084fc,stroke:#a855f7,color:#1e293b
```

---

## 6. Ambiente Local e Containers

O ambiente de desenvolvimento local executa de forma conteinerizada com isolamento de rede:

```mermaid
graph LR
    subgraph Docker Compose
        subgraph localstack["📦 localstack:4566"]
            DDB["DynamoDB<br/>pix_transactions_store"]
        end
        subgraph app["📦 app:8000"]
            UV["Uvicorn"]
            FA["FastAPI"]
            MG["Mangum"]
        end
    end

    app -- "aioboto3 → http://localstack:4566" --> localstack
    init["🔧 init-aws.sh"] -.->|"awslocal create-table"| DDB

    User["🧑‍💻 localhost:8000"] --> app
```

---

## 7. Dependências dos Módulos Internos

```mermaid
graph TD
    main["src/main.py<br/><i>FastAPI + Mangum</i>"]
    service["src/services/pix_service.py<br/><i>PixService</i>"]
    repo["src/repository/dynamodb.py<br/><i>PixRepository</i>"]
    models["src/models/pix.py<br/><i>Pydantic Models</i>"]
    config["src/config.py<br/><i>Settings</i>"]

    main --> service
    main --> models
    service --> repo
    service --> models
    service --> config
    repo --> config
```

---

## 8. Como Executar o Projeto Localmente

### Pré-requisitos
- Docker & Docker Compose instalados.

### Passos rápidos
1. Inicie a infraestrutura e a API FastAPI local:
   ```bash
   make up
   ```
2. Após o container `pix_localstack` estar saudável, a tabela do DynamoDB `pix_transactions_store` será criada de forma automática através do script `init-aws.sh`.
3. Verifique os logs se necessário:
   ```bash
   make logs
   ```
4. Desligue a infraestrutura e limpe os volumes:
   ```bash
   make down
   ```

---

## 9. Executando os Testes e Validação do Contrato

O projeto conta com testes de contrato orientados a propriedades (Fuzzing) utilizando o **Schemathesis** para garantir que a aplicação segue 100% o arquivo `specs/openapi.yaml`, além de testes de integração e testes unitários.

```bash
# Ative seu ambiente virtual de desenvolvimento (.venv)
source .venv/bin/activate

# Execute a suíte de testes completa
make test
```

---

## 10. Exemplos de Uso (API Endpoints)

### Chamada com sucesso (201 Created)
```bash
curl -i -X POST http://localhost:8000/v1/transfers \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: e80f2d91-3b47-4952-ba63-00e964bfa123" \
  -d '{
    "account_id": "acc-998877",
    "amount": 2500.00,
    "pix_key": "user@example.com",
    "pix_key_type": "EMAIL"
  }'
```

### Limite diário excedido (400 Bad Request)
```bash
curl -i -X POST http://localhost:8000/v1/transfers \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: c9d7f4be-990a-48d6-953e-52dbf11ea345" \
  -d '{
    "account_id": "acc-998877",
    "amount": 4900.00,
    "pix_key": "user@example.com",
    "pix_key_type": "EMAIL"
  }'
```

### Violação de Contrato (422 Unprocessable Entity)
```bash
curl -i -X POST http://localhost:8000/v1/transfers \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: 15fd42c6-d98c-42b7-a39c-5e58c1df245b" \
  -d '{
    "account_id": "acc-998877",
    "amount": 7500.00,
    "pix_key": "user@example.com",
    "pix_key_type": "EMAIL"
  }'
```

---

## 11. Estrutura de Diretórios do Projeto

```text
pix-authorizer-sdd/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
├── README.md
├── BUSINESS_REQUIREMENTS.md
├── PROJECT_RULES.md
├── TECHNICAL_DESIGN.md
├── specs/
│   └── openapi.yaml
├── scripts/
│   └── init-aws.sh
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── pix.py
│   ├── repository/
│   │   ├── __init__.py
│   │   └── dynamodb.py
│   └── services/
│       ├── __init__.py
│       └── pix_service.py
└── tests/
    ├── __init__.py
    └── test_contract.py
```
