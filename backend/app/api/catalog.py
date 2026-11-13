from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import any_role, staff_only
from app.core.database import get_db
from app.domain.errors import BusinessRuleError
from app.domain.isbn import is_valid_isbn
from app.integrations import openlibrary
from app.models import Author, Category, Copy
from app.schemas import (
    AuthorIn,
    AuthorOut,
    BookIn,
    BookOut,
    CategoryIn,
    CategoryOut,
    CopyIn,
    CopyOut,
    CopyStatusUpdate,
    IsbnLookupOut,
    Page,
)
from app.services import catalog
from app.services.audit import Actor

router = APIRouter(prefix="/api", tags=["Catalogue"])


# ------------------------------------------------------------------ catégories
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: Actor = Depends(any_role)) -> list[Category]:
    return catalog.list_categories(db)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryIn, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Category:
    return catalog.create_category(db, actor, data)


@router.put("/categories/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    data: CategoryIn,
    db: Session = Depends(get_db),
    actor: Actor = Depends(staff_only),
) -> Category:
    return catalog.update_category(db, actor, cat_id, data)


@router.delete("/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    cat_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> None:
    catalog.delete_category(db, actor, cat_id)


# ------------------------------------------------------------------ auteurs
@router.get("/authors", response_model=list[AuthorOut])
def list_authors(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _: Actor = Depends(any_role),
) -> list[Author]:
    return catalog.list_authors(db, q)


@router.post("/authors", response_model=AuthorOut, status_code=status.HTTP_201_CREATED)
def create_author(
    data: AuthorIn, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Author:
    return catalog.create_author(db, actor, data)


@router.put("/authors/{author_id}", response_model=AuthorOut)
def update_author(
    author_id: int,
    data: AuthorIn,
    db: Session = Depends(get_db),
    actor: Actor = Depends(staff_only),
) -> Author:
    return catalog.update_author(db, actor, author_id, data)


@router.delete("/authors/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(
    author_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> None:
    catalog.delete_author(db, actor, author_id)


# ------------------------------------------------------------------ ouvrages
@router.get("/books", response_model=Page[BookOut])
def search_books(
    q: str | None = Query(default=None, max_length=100),
    category_id: int | None = None,
    author_id: int | None = None,
    year_from: int | None = Query(default=None, ge=1450, le=2100),
    year_to: int | None = Query(default=None, ge=1450, le=2100),
    available_only: bool = False,
    sort: str = Query(default="title", pattern="^(title|year|-year|-created)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Actor = Depends(any_role),
) -> Page[BookOut]:
    rows, total = catalog.search_books(
        db,
        q=q,
        category_id=category_id,
        author_id=author_id,
        year_from=year_from,
        year_to=year_to,
        available_only=available_only,
        sort=sort,
        page=page,
        size=size,
    )
    return Page[BookOut](items=catalog.to_book_out(db, rows), total=total, page=page, size=size)


@router.get("/books/lookup/{isbn}", response_model=IsbnLookupOut)
def lookup_isbn(isbn: str, _: Actor = Depends(staff_only)) -> IsbnLookupOut:
    """Pré-remplissage via le service tiers Open Library (repli si indisponible)."""
    if not is_valid_isbn(isbn):
        raise BusinessRuleError("RG-01", "ISBN invalide (clé de contrôle incorrecte).")
    return openlibrary.lookup_isbn(isbn)


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db), _: Actor = Depends(any_role)) -> BookOut:
    return catalog.to_book_out(db, [catalog.get_book(db, book_id)])[0]


@router.post("/books", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(
    data: BookIn, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> BookOut:
    return catalog.to_book_out(db, [catalog.create_book(db, actor, data)])[0]


@router.put("/books/{book_id}", response_model=BookOut)
def update_book(
    book_id: int, data: BookIn, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> BookOut:
    return catalog.to_book_out(db, [catalog.update_book(db, actor, book_id, data)])[0]


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> None:
    catalog.delete_book(db, actor, book_id)


# ------------------------------------------------------------------ exemplaires
@router.get("/books/{book_id}/copies", response_model=list[CopyOut])
def list_copies(
    book_id: int, db: Session = Depends(get_db), _: Actor = Depends(any_role)
) -> list[Copy]:
    return catalog.list_copies(db, book_id)


@router.post("/books/{book_id}/copies", response_model=CopyOut, status_code=status.HTTP_201_CREATED)
def add_copy(
    book_id: int, data: CopyIn, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> Copy:
    return catalog.add_copy(db, actor, book_id, data)


@router.patch("/copies/{copy_id}", response_model=CopyOut)
def change_copy_status(
    copy_id: int,
    data: CopyStatusUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(staff_only),
) -> Copy:
    return catalog.change_copy_status(db, actor, copy_id, data.status)


@router.delete("/copies/{copy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_copy(
    copy_id: int, db: Session = Depends(get_db), actor: Actor = Depends(staff_only)
) -> None:
    catalog.delete_copy(db, actor, copy_id)
