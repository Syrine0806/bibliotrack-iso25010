"""Modèle de données relationnel (cf. diagramme ER dans docs/RAPPORT_CONCEPTION.md)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import clock
from app.core.database import Base
from app.domain.enums import CopyStatus, LoanStatus, PenaltyStatus, ReservationStatus, Role


def _enum(enum_cls):
    return Enum(enum_cls, native_enum=False, length=20, validate_strings=True)


# Relation N-N Livre ↔ Auteur
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="RESTRICT"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.ADHERENT)
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)

    loans: Mapped[list["Loan"]] = relationship(back_populates="user")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")
    penalties: Mapped[list["Penalty"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    books: Mapped[list["Book"]] = relationship(back_populates="category")


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    nationality: Mapped[str | None] = mapped_column(String(60), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    books: Mapped[list["Book"]] = relationship(secondary=book_authors, back_populates="authors")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    publisher: Mapped[str | None] = mapped_column(String(120), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)

    category: Mapped[Category] = relationship(back_populates="books")
    authors: Mapped[list[Author]] = relationship(secondary=book_authors, back_populates="books")
    copies: Mapped[list["Copy"]] = relationship(back_populates="book")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="book")

    __table_args__ = (Index("ix_books_category_year", "category_id", "publication_year"),)


class Copy(Base):
    """Exemplaire physique d'un ouvrage."""

    __tablename__ = "copies"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="RESTRICT"), index=True)
    barcode: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[CopyStatus] = mapped_column(
        _enum(CopyStatus), default=CopyStatus.DISPONIBLE, index=True
    )
    shelf_location: Mapped[str | None] = mapped_column(String(40), nullable=True)
    acquired_on: Mapped[date] = mapped_column(Date, default=clock.today)

    book: Mapped[Book] = relationship(back_populates="copies")
    loans: Mapped[list["Loan"]] = relationship(back_populates="copy")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    copy_id: Mapped[int] = mapped_column(ForeignKey("copies.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    loaned_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    renewals_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[LoanStatus] = mapped_column(
        _enum(LoanStatus), default=LoanStatus.EN_COURS, index=True
    )

    copy: Mapped[Copy] = relationship(back_populates="loans")
    user: Mapped[User] = relationship(back_populates="loans")
    penalties: Mapped[list["Penalty"]] = relationship(back_populates="loan")

    # Garantie au niveau base (fiabilité) : au plus UN prêt actif par exemplaire,
    # même en cas de requêtes concurrentes.
    __table_args__ = (
        Index(
            "uq_loans_active_copy",
            "copy_id",
            unique=True,
            sqlite_where=text("status IN ('EN_COURS', 'EN_RETARD')"),
            postgresql_where=text("status IN ('EN_COURS', 'EN_RETARD')"),
        ),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    copy_id: Mapped[int | None] = mapped_column(
        ForeignKey("copies.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ReservationStatus] = mapped_column(
        _enum(ReservationStatus), default=ReservationStatus.EN_ATTENTE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    available_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    book: Mapped[Book] = relationship(back_populates="reservations")
    user: Mapped[User] = relationship(back_populates="reservations")
    copy: Mapped[Copy | None] = relationship()

    # Une seule réservation active par (adhérent, ouvrage).
    __table_args__ = (
        Index(
            "uq_reservations_active_user_book",
            "user_id",
            "book_id",
            unique=True,
            sqlite_where=text("status IN ('EN_ATTENTE', 'DISPONIBLE')"),
            postgresql_where=text("status IN ('EN_ATTENTE', 'DISPONIBLE')"),
        ),
    )


class Penalty(Base):
    __tablename__ = "penalties"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    loan_id: Mapped[int | None] = mapped_column(
        ForeignKey("loans.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="AUTRE")  # RETARD | PERTE | AUTRE
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[PenaltyStatus] = mapped_column(
        _enum(PenaltyStatus), default=PenaltyStatus.IMPAYEE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="penalties")
    loan: Mapped[Loan | None] = relationship(back_populates="penalties")

    __table_args__ = (UniqueConstraint("loan_id", "kind", name="uq_penalty_loan_kind"),)


class AuditLog(Base):
    """Journal d'audit des actions sensibles (qui, quoi, quand, sur quoi)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
