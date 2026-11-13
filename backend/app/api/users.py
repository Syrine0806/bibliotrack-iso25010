from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import admin_only, staff_only
from app.core.database import get_db
from app.domain.enums import Role
from app.models import User
from app.schemas import Page, UserCreate, UserOut, UserUpdate
from app.services import users
from app.services.audit import Actor

router = APIRouter(prefix="/api/users", tags=["Utilisateurs"])


@router.get("", response_model=Page[UserOut])
def list_users(
    q: str | None = Query(default=None, max_length=100),
    role: Role | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Actor = Depends(staff_only),
) -> Page[UserOut]:
    rows, total = users.list_users(db, q, role, page, size)
    return Page[UserOut](items=rows, total=total, page=page, size=size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate, db: Session = Depends(get_db), actor: Actor = Depends(admin_only)
) -> User:
    return users.create_user(db, actor, data)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: Actor = Depends(staff_only)) -> User:
    return users.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(admin_only),
) -> User:
    return users.update_user(db, actor, user_id, data)


@router.post("/{user_id}/unlock", response_model=UserOut)
def unlock_user(
    user_id: int, db: Session = Depends(get_db), actor: Actor = Depends(admin_only)
) -> User:
    return users.unlock_user(db, actor, user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, db: Session = Depends(get_db), actor: Actor = Depends(admin_only)
) -> None:
    users.delete_user(db, actor, user_id)
