from fastapi import FastAPI, Header, Request, status
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.models.pix import ErrorResponse, TransferRequest, TransferResponse
from src.exceptions import DailyLimitExceededException
from src.repository.dynamodb import PixRepository
from src.services.pix_service import PixService

app = FastAPI(
    title="Pix Authorizer API",
    version="1.0.0",
    description="API de autorização de transações PIX com idempotência e controle de limite diário.",
)
app.openapi_version = "3.0.3"

pix_service = PixService(repository=PixRepository())


@app.exception_handler(DailyLimitExceededException)
async def daily_limit_exceeded_handler(
    request: Request, exc: DailyLimitExceededException
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.post(
    "/v1/transfers",
    status_code=status.HTTP_201_CREATED,
    response_model=TransferResponse,
    responses={
        status.HTTP_201_CREATED: {
            "model": TransferResponse,
            "description": "Transferência Aprovada",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Recusado por regra de negócio",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Erro de Validação de Schema",
        },
    },
)
async def create_transfer(
    request: TransferRequest,
    x_idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
) -> TransferResponse:
    return await pix_service.process_transfer(
        request=request, idempotency_key=x_idempotency_key
    )


handler = Mangum(app, lifespan="off")
