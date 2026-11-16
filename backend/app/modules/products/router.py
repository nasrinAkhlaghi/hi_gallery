"""Product management for approved sellers, categories and local image delivery."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import StringConstraints

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.auth.models import Account
from app.modules.auth.schemas import Role
from app.modules.categories.models import Category
from app.modules.products import service, storage, public_service
from app.modules.products.models import ProductImage
from app.modules.products.schemas import CategoryList, ImageResponse, ProductList, ProductResponse, ProductStatus, ProductWrite
from app.modules.products.schemas import PublicProductList, PublicProductResponse
from app.modules.seller import service as seller_service

router = APIRouter(prefix="/api/v1", tags=["seller products"])
media_router = APIRouter(tags=["product media"])
public_router = APIRouter(prefix="/api/v1", tags=["public products"])
DbSession = Annotated[Session, Depends(get_db)]
ActiveSeller = Annotated[Account, Depends(require_roles(Role.SELLER, active_seller=True))]
Page = Annotated[int, Query(ge=0)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200), Query()]


def perform(action):
    try:
        return action()
    except service.ProductError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code}) from None


@public_router.get("/products", response_model=PublicProductList)
def browse_products(session: DbSession, page: Page = 0, page_size: PageSize = 20,
                    q: Search | None = None, category_id: UUID | None = None):
    return public_service.list_products(session, page, page_size, q=q, category_id=category_id)


@public_router.get("/products/{product_id}", response_model=PublicProductResponse)
def public_product_detail(product_id: UUID, session: DbSession):
    return perform(lambda: public_service.product_detail(session, product_id))


@public_router.get("/shops/{seller_id}/products", response_model=PublicProductList)
def shop_products(seller_id: UUID, session: DbSession, page: Page = 0, page_size: PageSize = 20,
                  category_id: UUID | None = None):
    try:
        seller_service.get_public_shop(session, seller_id)
    except seller_service.SellerProfileNotFound:
        raise HTTPException(404, detail={"code": "SHOP_NOT_FOUND"}) from None
    return public_service.list_products(session, page, page_size, seller_id=seller_id, category_id=category_id)


@public_router.get("/categories/{category_id}/products", response_model=PublicProductList)
def category_products(category_id: UUID, session: DbSession, page: Page = 0, page_size: PageSize = 20):
    perform(lambda: public_service.require_active_category(session, category_id))
    return public_service.list_products(session, page, page_size, category_id=category_id)


@router.get("/categories", response_model=CategoryList)
def categories(session: DbSession, page: Page = 0, page_size: PageSize = 20):
    active = Category.status == "ACTIVE"
    return {"items": session.scalars(select(Category).where(active).order_by(Category.name, Category.id)
                                     .offset(page * page_size).limit(page_size)).all(),
            "total": session.scalar(select(func.count()).select_from(Category).where(active)),
            "page": page, "page_size": page_size}


@router.get("/seller/products", response_model=ProductList)
def products(session: DbSession, account: ActiveSeller, page: Page = 0, page_size: PageSize = 20,
             status: ProductStatus | None = None):
    return service.list_products(session, account.seller.id, page, page_size, status)


@router.post("/seller/products", response_model=ProductResponse, status_code=201)
def create_product(body: ProductWrite, session: DbSession, account: ActiveSeller):
    return perform(lambda: service.save_product(session, account.seller.id, body))


@router.get("/seller/products/{product_id}", response_model=ProductResponse)
def product_detail(product_id: UUID, session: DbSession, account: ActiveSeller):
    return perform(lambda: service.owned_product(session, account.seller.id, product_id))


@router.put("/seller/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: UUID, body: ProductWrite, session: DbSession, account: ActiveSeller):
    return perform(lambda: service.save_product(session, account.seller.id, body, product_id))


@router.delete("/seller/products/{product_id}", status_code=204)
def remove_product(product_id: UUID, session: DbSession, account: ActiveSeller):
    perform(lambda: service.delete_product(session, account.seller.id, product_id))
    return Response(status_code=204)


@router.post("/seller/products/{product_id}/images", response_model=ImageResponse, status_code=201)
async def upload_image(product_id: UUID, request: Request, session: DbSession, account: ActiveSeller):
    perform(lambda: service.owned_product(session, account.seller.id, product_id))
    if get_settings().environment == "production":
        raise HTTPException(503, detail={"code": "LOCAL_UPLOADS_DEVELOPMENT_ONLY"})
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in {item[1] for item in storage.FORMATS.values()}:
        raise HTTPException(422, detail={"code": "INVALID_PRODUCT_IMAGE"})
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > storage.MAX_IMAGE_BYTES:
            raise HTTPException(413, detail={"code": "PRODUCT_IMAGE_TOO_LARGE"})
        data.extend(chunk)
    return perform(lambda: service.add_image(session, account.seller.id, product_id, bytes(data), content_type))


@router.delete("/seller/products/{product_id}/images/{image_id}", status_code=204)
def remove_product_image(product_id: UUID, image_id: UUID, session: DbSession, account: ActiveSeller):
    perform(lambda: service.delete_image(session, account.seller.id, product_id, image_id))
    return Response(status_code=204)


@media_router.get("/media/products/{filename}", include_in_schema=False)
def image_file(filename: str, session: DbSession):
    path = storage.image_path(filename)
    if path is None or not path.is_file() or session.scalar(
        select(ProductImage.id).where(ProductImage.url == storage.MEDIA_PREFIX + filename).limit(1)
    ) is None:
        raise HTTPException(404, detail={"code": "PRODUCT_IMAGE_NOT_FOUND"})
    return FileResponse(path, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"})
