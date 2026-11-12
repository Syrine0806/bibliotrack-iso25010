"""Schémas d'entrée/sortie de l'API (contrat d'interface validé par Pydantic)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.core.security import password_is_strong
from app.domain.enums import CopyStatus, LoanStatus, PenaltyStatus, ReservationStatus, Role
from app.domain.isbn import is_valid_isbn, to_isbn13

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


# ------------------------------------------------------------------ auth / utilisateurs
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - type de jeton OAuth2, pas un secret
    role: Role
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _check_password(v: str) -> str:
    if not password_is_strong(v):
        raise ValueError(
            "Mot de passe invalide : 8 caractères minimum (72 octets maximum), lettres et chiffres."
        )
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: Name
    password: str

    _pw = field_validator("password")(_check_password)


class UserCreate(RegisterRequest):
    role: Role = Role.ADHERENT


class UserUpdate(BaseModel):
    full_name: Name | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str | None) -> str | None:
        return None if v is None else _check_password(v)


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    locked_until: datetime | None = None
    created_at: datetime


# ------------------------------------------------------------------ catalogue
class CategoryIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    description: str | None = Field(default=None, max_length=255)


class CategoryOut(ORMModel):
    id: int
    name: str
    description: str | None


class AuthorIn(BaseModel):
    full_name: Name
    nationality: str | None = Field(default=None, max_length=60)
    birth_year: int | None = Field(default=None, ge=-2000, le=2100)


class AuthorOut(ORMModel):
    id: int
    full_name: str
    nationality: str | None
    birth_year: int | None


class BookIn(BaseModel):
    isbn: str
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    publisher: str | None = Field(default=None, max_length=120)
    publication_year: int | None = Field(default=None, ge=1450, le=2100)
    summary: str | None = Field(default=None, max_length=5000)
    category_id: int
    author_ids: list[int] = Field(min_length=1)

    @field_validator("isbn")
    @classmethod
    def _isbn(cls, v: str) -> str:
        if not is_valid_isbn(v):
            raise ValueError("ISBN invalide (clé de contrôle incorrecte) — règle RG-01.")
        return to_isbn13(v)


class BookOut(ORMModel):
    id: int
    isbn: str
    title: str
    publisher: str | None
    publication_year: int | None
    summary: str | None
    category: CategoryOut
    authors: list[AuthorOut]
    total_copies: int = 0
    available_copies: int = 0


class CopyIn(BaseModel):
    barcode: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z0-9-]{4,32}$")]
    shelf_location: str | None = Field(default=None, max_length=40)


class CopyStatusUpdate(BaseModel):
    status: CopyStatus


class CopyOut(ORMModel):
    id: int
    book_id: int
    barcode: str
    status: CopyStatus
    shelf_location: str | None
    acquired_on: date


# ------------------------------------------------------------------ prêts / réservations
class LoanCreate(BaseModel):
    user_id: int
    barcode: str = Field(min_length=4, max_length=32)


class BookBrief(ORMModel):
    id: int
    isbn: str
    title: str


class CopyBrief(ORMModel):
    id: int
    barcode: str
    book: BookBrief


class UserBrief(ORMModel):
    id: int
    email: str
    full_name: str


class LoanOut(ORMModel):
    id: int
    status: LoanStatus
    loaned_at: datetime
    due_date: date
    returned_at: datetime | None
    renewals_count: int
    item: CopyBrief = Field(validation_alias="copy")
    user: UserBrief


class ReturnResult(BaseModel):
    loan: LoanOut
    penalty_amount: Decimal
    days_late: int
    reserved_for_user_id: int | None = None


class ReservationCreate(BaseModel):
    book_id: int
    user_id: int | None = None  # utilisé par le personnel pour réserver pour un adhérent


class ReservationOut(ORMModel):
    id: int
    status: ReservationStatus
    created_at: datetime
    available_until: datetime | None
    book: BookBrief
    user: UserBrief
    copy_id: int | None
    queue_position: int | None = None


class PenaltyCreate(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0, le=1000, decimal_places=2)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]


class PenaltyOut(ORMModel):
    id: int
    kind: str
    amount: Decimal
    reason: str
    status: PenaltyStatus
    created_at: datetime
    settled_at: datetime | None
    loan_id: int | None
    user: UserBrief


# ------------------------------------------------------------------ audit / dashboard
class AuditOut(ORMModel):
    id: int
    timestamp: datetime
    user_id: int | None
    user_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    ip_address: str | None


class CountItem(BaseModel):
    label: str
    value: int


class DashboardOut(BaseModel):
    total_books: int
    total_copies: int
    available_copies: int
    active_loans: int
    overdue_loans: int
    active_members: int
    pending_reservations: int
    unpaid_penalties_total: Decimal
    loans_in_period: int
    loans_by_month: list[CountItem]
    top_books: list[CountItem]
    loans_by_category: list[CountItem]
    copies_by_status: list[CountItem]


class IsbnLookupOut(BaseModel):
    isbn: str
    found: bool
    source: str
    title: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    authors: list[str] = []
    message: str | None = None
