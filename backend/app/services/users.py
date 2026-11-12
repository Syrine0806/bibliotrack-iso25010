"""Authentification (avec verrouillage RG-10) et gestion des utilisateurs (RG-09)."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.enums import ACTIVE_LOAN_STATUSES, PenaltyStatus, Role
from app.domain.errors import BusinessRuleError, NotFoundError
from app.models import Loan, Penalty, Reservation, User
from app.schemas import RegisterRequest, Token, UserCreate, UserUpdate
from app.services import audit
from app.services.audit import Actor


class AuthenticationError(Exception):
    """Identifiants invalides ou compte verrouillé (message volontairement générique)."""


GENERIC_AUTH_ERROR = "Identifiants invalides ou compte verrouillé."


def _register_failure(db: Session, user: User, ip: str | None) -> None:
    settings = get_settings()
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.max_failed_logins:
        user.locked_until = clock.now() + timedelta(minutes=settings.lockout_minutes)
        user.failed_login_attempts = 0
        audit.record(
            db,
            Actor(user.id, user.email, user.role, ip),
            "ACCOUNT_LOCKED",
            "User",
            user.id,
            until=user.locked_until,
        )
    audit.record(db, Actor(user.id, user.email, user.role, ip), "LOGIN_FAILED", "User", user.id)
    db.commit()


def authenticate(db: Session, email: str, password: str, ip: str | None = None) -> Token:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        audit.record(db, Actor(None, email.lower(), None, ip), "LOGIN_FAILED", "User")
        db.commit()
        raise AuthenticationError(GENERIC_AUTH_ERROR)
    if user.locked_until and user.locked_until > clock.now():
        audit.record(
            db, Actor(user.id, user.email, user.role, ip), "LOGIN_REFUSED_LOCKED", "User", user.id
        )
        db.commit()
        raise AuthenticationError(GENERIC_AUTH_ERROR)
    if not verify_password(password, user.hashed_password) or not user.is_active:
        _register_failure(db, user, ip)
        raise AuthenticationError(GENERIC_AUTH_ERROR)
    user.failed_login_attempts = 0
    user.locked_until = None
    audit.record(db, Actor(user.id, user.email, user.role, ip), "LOGIN_SUCCESS", "User", user.id)
    db.commit()
    return Token(
        access_token=create_access_token(str(user.id), user.role.value),
        role=user.role,
        full_name=user.full_name,
    )


def _insert_user(db: Session, data: RegisterRequest, role: Role) -> User:
    user = User(
        email=str(data.email).lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise BusinessRuleError("RG-12", "Un compte existe déjà avec cet e-mail.") from exc
    return user


def register(db: Session, data: RegisterRequest, ip: str | None = None) -> User:
    """Inscription libre : toujours en tant qu'ADHERENT (pas d'élévation de privilège)."""
    user = _insert_user(db, data, Role.ADHERENT)
    audit.record(db, Actor(user.id, user.email, user.role, ip), "USER_REGISTERED", "User", user.id)
    db.commit()
    return user


def create_user(db: Session, actor: Actor, data: UserCreate) -> User:
    user = _insert_user(db, data, data.role)
    audit.record(db, actor, "USER_CREATED", "User", user.id, email=user.email, role=user.role)
    db.commit()
    return user


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Utilisateur", user_id)
    return user


def list_users(
    db: Session, q: str | None, role: Role | None, page: int, size: int
) -> tuple[list[User], int]:
    stmt = select(User)
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    if role:
        stmt = stmt.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.full_name).offset((page - 1) * size).limit(size)).all()
    return list(rows), total


def update_user(db: Session, actor: Actor, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if actor.id == user.id and (
        changes.get("role", user.role) != user.role or changes.get("is_active") is False
    ):
        raise BusinessRuleError("RG-09", "Un administrateur ne peut pas se rétrograder/désactiver.")
    if "password" in changes:
        user.hashed_password = hash_password(changes.pop("password"))
        # Revue sécurité : "***" est un masque écrit dans le journal d'audit, pas un secret.
        changes["password"] = "***"  # noqa: S105  # nosec B105
    for field in ("full_name", "role", "is_active"):
        if field in changes:
            setattr(user, field, changes[field])
    audit.record(db, actor, "USER_UPDATED", "User", user.id, **changes)
    db.commit()
    return user


def unlock_user(db: Session, actor: Actor, user_id: int) -> User:
    user = get_user(db, user_id)
    user.locked_until = None
    user.failed_login_attempts = 0
    audit.record(db, actor, "USER_UNLOCKED", "User", user.id)
    db.commit()
    return user


def unpaid_total(db: Session, user_id: int) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Penalty.amount), 0)).where(
            Penalty.user_id == user_id, Penalty.status == PenaltyStatus.IMPAYEE
        )
    )
    return Decimal(str(total or 0))


def delete_user(db: Session, actor: Actor, user_id: int) -> None:
    """RG-09 : suppression refusée si emprunts actifs ou pénalités impayées."""
    user = get_user(db, user_id)
    if actor.id == user.id:
        raise BusinessRuleError("RG-09", "Impossible de supprimer son propre compte.")
    active = db.scalar(
        select(func.count()).where(Loan.user_id == user_id, Loan.status.in_(ACTIVE_LOAN_STATUSES))
    )
    if active or unpaid_total(db, user_id) > 0:
        raise BusinessRuleError(
            "RG-09", "Suppression impossible : emprunts en cours ou pénalités impayées."
        )
    has_history = any(
        db.scalar(select(func.count()).where(model.user_id == user_id))
        for model in (Loan, Penalty, Reservation)
    )
    if has_history:
        # Conservation de l'historique : désactivation logique plutôt que suppression physique.
        user.is_active = False
        audit.record(db, actor, "USER_DEACTIVATED", "User", user.id, reason="historique")
    else:
        audit.record(db, actor, "USER_DELETED", "User", user.id, email=user.email)
        db.delete(user)
    db.commit()
