"""Seller-owned product operations. All mutation lookups lock the product row."""

from datetime import datetime, timezone
import logging
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.cart.models import CartItem
from app.modules.categories.models import Category
from app.modules.orders.models import OrderItem
from app.modules.products.models import Product, ProductImage
from app.modules.products.schemas import ProductWrite
from app.modules.products import storage
from app.modules.reviews.models import Review

logger = logging.getLogger(__name__)


class ProductError(Exception):
    def __init__(self, code: str, status: int):
        self.code, self.status = code, status


def owned_product(session: Session, seller_id: UUID, product_id: UUID, *, lock: bool = False) -> Product:
    query = select(Product).where(Product.id == product_id, Product.seller_id == seller_id)
    if lock:
        query = query.with_for_update()
    product = session.scalar(query.options(selectinload(Product.images)).execution_options(populate_existing=True))
    if product is None:
        raise ProductError("PRODUCT_NOT_FOUND", 404)
    product.images.sort(key=lambda image: (image.sort_order, image.id))
    return product


def list_products(session: Session, seller_id: UUID, page: int, page_size: int, status: str | None) -> dict:
    filters = [Product.seller_id == seller_id]
    if status is not None:
        filters.append(Product.status == status)
    total = session.scalar(select(func.count()).select_from(Product).where(*filters))
    products = session.scalars(
        select(Product).where(*filters).options(selectinload(Product.images))
        .order_by(Product.created_at.desc(), Product.id).offset(page * page_size).limit(page_size)
    ).all()
    for product in products:
        product.images.sort(key=lambda image: (image.sort_order, image.id))
    return {"items": products, "total": total, "page": page, "page_size": page_size}


def save_product(session: Session, seller_id: UUID, body: ProductWrite, product_id: UUID | None = None) -> Product:
    product = owned_product(session, seller_id, product_id, lock=True) if product_id else None
    category = session.get(Category, body.category_id)
    # Existing assignments remain editable if a category is later disabled.
    if category is None or (category.status != "ACTIVE" and (product is None or product.category_id != category.id)):
        raise ProductError("CATEGORY_UNAVAILABLE", 422)
    now = datetime.now(timezone.utc)
    if product is None:
        product = Product(id=uuid4(), seller_id=seller_id, created_at=now, updated_at=now, **body.model_dump())
        session.add(product)
    else:
        for field, value in body.model_dump().items():
            setattr(product, field, value)
        product.updated_at = now
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return owned_product(session, seller_id, product.id)


def cleanup_files(urls: list[str]) -> None:
    for url in urls:
        try:
            storage.remove_image(url)
        except OSError:
            # A cleanup failure must not misreport a committed deletion as failed.
            logger.exception("Could not remove orphaned local product image")


def delete_product(session: Session, seller_id: UUID, product_id: UUID) -> None:
    product = owned_product(session, seller_id, product_id, lock=True)
    for model in (CartItem, OrderItem, Review):
        if session.scalar(select(model.id).where(model.product_id == product_id).limit(1)) is not None:
            raise ProductError("PRODUCT_IN_USE", 409)
    urls = [image.url for image in product.images]
    try:
        # Core DELETE leaves referenced rows intact; FK races return a conflict.
        session.execute(delete(ProductImage).where(ProductImage.product_id == product_id))
        session.execute(delete(Product).where(Product.id == product_id, Product.seller_id == seller_id))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ProductError("PRODUCT_IN_USE", 409) from None
    except Exception:
        session.rollback()
        raise
    cleanup_files(urls)


def add_image(session: Session, seller_id: UUID, product_id: UUID, data: bytes, content_type: str) -> ProductImage:
    product = owned_product(session, seller_id, product_id, lock=True)
    try:
        url = storage.store_image(data, content_type)
    except storage.InvalidImage:
        raise ProductError("INVALID_PRODUCT_IMAGE", 422) from None
    image = ProductImage(id=uuid4(), product_id=product.id, url=url,
                         sort_order=max((item.sort_order for item in product.images), default=-1) + 1)
    product.updated_at = datetime.now(timezone.utc)
    session.add(image)
    try:
        session.commit()
        session.refresh(image)
    except Exception:
        session.rollback()
        cleanup_files([url])
        raise
    return image


def delete_image(session: Session, seller_id: UUID, product_id: UUID, image_id: UUID) -> None:
    product = owned_product(session, seller_id, product_id, lock=True)
    image = next((item for item in product.images if item.id == image_id), None)
    if image is None:
        raise ProductError("PRODUCT_IMAGE_NOT_FOUND", 404)
    url = image.url
    product.updated_at = datetime.now(timezone.utc)
    session.delete(image)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    cleanup_files([url])
