from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, Token, UserOut
from app.services import users

router = APIRouter(prefix="/api/auth", tags=["Authentification"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    try:
        return users.authenticate(db, str(data.email), data.password, client_ip(request))
    except users.AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> User:
    return users.register(db, data, client_ip(request))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
