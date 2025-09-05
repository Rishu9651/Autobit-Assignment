from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class UserProvider(str, Enum):
    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"


class ServerStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"


class TransactionMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"


# User Models
class UserBase(BaseModel):
    email: EmailStr
    name: str
    provider: UserProvider
    provider_id: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = None


class UserInDB(UserBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(UserBase):
    id: str
    created_at: datetime


# Server Models
class ServerBase(BaseModel):
    name: str
    image: str
    cpu_limit: float
    cores: int
    ram_gib: float
    disk_gib: float


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    cpu_limit: Optional[float] = None
    cores: Optional[int] = None
    ram_gib: Optional[float] = None
    disk_gib: Optional[float] = None


class ServerInDB(ServerBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: ServerStatus = ServerStatus.CREATED
    container_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Server(ServerBase):
    id: str
    user_id: str
    status: ServerStatus
    container_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Usage Models
class UsageSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    cpu_pct: float
    ram_mib: float
    disk_gib: float


# Billing Models
class LineItem(BaseModel):
    kind: str  # "vCPU", "RAM", "Disk"
    unit: str  # "core-hour", "gib-hour"
    quantity: float
    rate: float
    amount: float


class InvoiceBase(BaseModel):
    user_id: str
    period_start: datetime
    period_end: datetime


class InvoiceInDB(InvoiceBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    line_items: List[LineItem] = []
    subtotal: float = 0.0
    total: float = 0.0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Invoice(InvoiceBase):
    id: str
    line_items: List[LineItem]
    subtotal: float
    total: float
    status: InvoiceStatus
    created_at: datetime


class TransactionBase(BaseModel):
    invoice_id: str
    amount: float
    method: TransactionMethod


class TransactionInDB(TransactionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)


class Transaction(TransactionBase):
    id: str
    ts: datetime


# Auth Models
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


# API Response Models
class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Dict[str, Any]] = None


# Billing Rates
class BillingRates(BaseModel):
    vcpu_rate_per_core_hour: float
    ram_rate_per_gib_hour: float
    disk_rate_per_gib_hour: float


# Usage Query
class UsageQuery(BaseModel):
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    interval: Optional[str] = "1h"  # 1m, 5m, 1h, 1d


# Invoice Generation
class InvoiceGenerateRequest(BaseModel):
    period_start: datetime
    period_end: datetime
