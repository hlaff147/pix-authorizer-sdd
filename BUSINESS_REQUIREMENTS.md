# Business Requirements Document (BRD) - Pix Authorizer Service

**Código da Demanda:** BRD-PIX-AUTHORIZER-001  
**Responsável Técnico:** Humberto — Engenharia de Software  
**Contexto:** Plataforma de Pagamentos e Core Bancário  

---

## 1. Objetivo de Negócio

Garantir a execução segura, confiável e idempotente de solicitações de transferência PIX, barrando transações fora das regras operacionais antes que elas atinjam os sistemas legados de liquidação bancária.

---

## 2. Regras de Negócio (Business Rules)

* **RN-001 (Limite Máximo por Transação):**
  * O valor individual de uma transferência não pode exceder **R$ 5.000,00**.
  * **Ação em caso de violação:** Rejeitar no gateway/validação com HTTP `422 Unprocessable Entity`.

* **RN-002 (Limite Acumulado Diário):**
  * O somatório das transações aprovadas de uma conta no mesmo dia civil não pode ultrapassar **R$ 20.000,00**.
  * **Ação em caso de violação:** Recusar a transação com HTTP `400 Bad Request` indicando "Limite diário excedido".

* **RN-003 (Idempotência Estrita):**
  * Toda requisição exige o envio do cabeçalho HTTP `X-Idempotency-Key` (UUIDv4).
  * Se a mesma chave for reenviada, a API deve retornar exatamente o mesmo payload e status code gerados na primeira execução válida, sem efetuar novo débito.

* **RN-004 (Validação de Chave PIX):**
  * A chave receptora deve pertencer a uma das categorias válidas: `CPF`, `CNPJ`, `EMAIL`, `PHONE` (padrão E.164) ou `EVP` (chave aleatória).

---

## 3. Critérios de Aceite

1. **Conformidade de Contrato:** 100% de aprovação na suíte de testes de contrato gerada automaticamente pelo Schemathesis a partir da OpenAPI.
2. **Proteção contra Double-Spending:** Duas requisições simultâneas com a mesma chave de idempotência resultam em apenas um registro efetivado no DynamoDB.
3. **Rastreabilidade:** Todas as operações (aprovadas ou recusadas) gravam um rastro auditável no banco de dados.
