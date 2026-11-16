"""Public discovery uses one eligibility query for lists, totals and detail."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from app.modules.auth.models import Account
from app.modules.categories.models import Category
from app.modules.products.models import Product
from app.modules.products.service import ProductError
from app.modules.seller.models import Seller
from app.modules.seller.service import public_seller_conditions


def visible_products():
    return (
        select(Product).join(Seller, Seller.id == Product.seller_id)
        .join(Account, Account.id == Seller.account_id)
        .where(*public_seller_conditions(), Product.status.in_(("ACTIVE", "SOLD_OUT")))
    )


def public_details(query):
    return query.options(contains_eager(Product.seller), joinedload(Product.category), selectinload(Product.images))


def sort_images(product: Product) -> Product:
    product.images.sort(key=lambda image: (image.sort_order, image.id))
    return product


def product_detail(session: Session, product_id: UUID) -> Product:
    product = session.scalar(public_details(visible_products().where(Product.id == product_id)))
    if product is None:
        raise ProductError("PRODUCT_NOT_FOUND", 404)
    return sort_images(product)


def list_products(session: Session, page: int, page_size: int, *, q: str | None = None,
                  category_id: UUID | None = None, seller_id: UUID | None = None) -> dict:
    query = visible_products()
    if seller_id is not None:
        query = query.where(Product.seller_id == seller_id)
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if q:
        query = query.where(Product.name.icontains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    products = session.scalars(
        public_details(query).order_by(Product.created_at.desc(), Product.id)
        .offset(page * page_size).limit(page_size)
    ).all()
    return {"items": [sort_images(product) for product in products], "total": total,
            "page": page, "page_size": page_size}


def require_active_category(session: Session, category_id: UUID) -> None:
    if session.scalar(select(Category.id).where(Category.id == category_id, Category.status == "ACTIVE")) is None:
        raise ProductError("CATEGORY_NOT_FOUND", 404)
