from enum import Enum
from pydantic import BaseModel, Field


class PixKeyType(str, Enum):
    CPF = "CPF"
    CNPJ = "CNPJ"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    EVP = "EVP"


class TransferStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TransferRequest(BaseModel):
    account_id: str = Field(..., description="Account identifier")
    amount: float = Field(
        ...,
        gt=0,
        le=5000.00,
        description="Transfer amount (max 5000.00)",
    )
    pix_key: str = Field(..., description="Destination PIX key")
    pix_key_type: PixKeyType = Field(..., description="Type of the destination PIX key")


class TransferResponse(BaseModel):
    transfer_id: str = Field(..., description="UUID of the transfer")
    account_id: str = Field(..., description="Account identifier")
    amount: float = Field(..., description="Transfer amount")
    pix_key: str = Field(..., description="Destination PIX key")
    pix_key_type: PixKeyType = Field(..., description="Type of the destination PIX key")
    status: TransferStatus = Field(..., description="Transaction approval status")
    created_at: str = Field(..., description="Timestamp of creation (ISO 8601)")


class ErrorResponse(BaseModel):
    error_code: str = Field(..., description="Error classification code")
    message: str = Field(..., description="User-friendly error message")
