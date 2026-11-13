"""Dépendances transverses : utilisateur courant (JWT) et contrôle d'accès par rôle (RBAC)."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.domain.enums import Role
from app.models import User
from app.services.audit import Actor

bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise ou jeton invalide.",
    headers={"WWW-Authenticate": "Bearer"},
)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UNAUTHORIZED
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise UNAUTHORIZED from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    request.state.user = user
    return user


def get_actor(request: Request, user: User = Depends(get_current_user)) -> Actor:
    return Actor(id=user.id, email=user.email, role=user.role, ip=client_ip(request))


def require_roles(*roles: Role) -> Callable[..., Actor]:
    """Fabrique de dépendance : 403 si le rôle de l'utilisateur n'est pas autorisé."""

    def checker(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Droits insuffisants pour cette action.",
            )
        return actor

    return checker


staff_only = require_roles(Role.ADMIN, Role.BIBLIOTHECAIRE)
admin_only = require_roles(Role.ADMIN)
any_role = require_roles(Role.ADMIN, Role.BIBLIOTHECAIRE, Role.ADHERENT)
