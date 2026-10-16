-- HI Gallery current schema reference after migrations 0001-0003.
-- The immutable 0001 initial-schema source remains backend/alembic/schema.sql.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE account (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_account_status CHECK (status IN ('ACTIVE','SUSPENDED','DELETED'))
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    replacement_token_id UUID UNIQUE REFERENCES refresh_tokens(id) ON DELETE SET NULL,
    reuse_detected_at TIMESTAMPTZ
);

CREATE TABLE buyer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL UNIQUE REFERENCES account(id),
    display_name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE seller (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL UNIQUE REFERENCES account(id),
    shop_name VARCHAR(150) NOT NULL,
    description TEXT,
    logo_url TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_seller_status CHECK (status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED'))
);

CREATE TABLE seller_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller(id),
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    actor_account_id UUID NOT NULL REFERENCES account(id),
    actor_type VARCHAR(20) NOT NULL,
    action VARCHAR(40) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_seller_status_history_previous_status CHECK (
        previous_status IS NULL OR previous_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')
    ),
    CONSTRAINT ck_seller_status_history_new_status CHECK (
        new_status IN ('DRAFT','PENDING','ACTIVE','SUSPENDED','REJECTED')
    ),
    CONSTRAINT ck_seller_status_history_actor_type CHECK (
        actor_type IN ('SELLER','ADMIN')
    )
);

CREATE TABLE admin (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL UNIQUE REFERENCES account(id),
    display_name VARCHAR(150) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE category (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID REFERENCES category(id),
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(180) NOT NULL UNIQUE,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_category_status CHECK (status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE product (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller(id),
    category_id UUID NOT NULL REFERENCES category(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(12,2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_product_price CHECK (price >= 0),
    CONSTRAINT ck_product_stock CHECK (stock >= 0),
    CONSTRAINT ck_product_status CHECK (status IN ('DRAFT','ACTIVE','INACTIVE','SOLD_OUT')),
    CONSTRAINT uk_product_id_seller UNIQUE (id,seller_id)
);

CREATE TABLE product_image (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT ck_product_image_sort_order CHECK (sort_order >= 0)
);

CREATE TABLE cart (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL UNIQUE REFERENCES buyer(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cart_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID NOT NULL REFERENCES cart(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES product(id),
    quantity INTEGER NOT NULL,
    UNIQUE (cart_id,product_id),
    CONSTRAINT ck_cart_item_quantity CHECK (quantity > 0)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES buyer(id),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    total_amount NUMERIC(12,2) NOT NULL,
    shipping_name VARCHAR(150) NOT NULL,
    shipping_phone VARCHAR(50) NOT NULL,
    shipping_address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_orders_total_amount CHECK (total_amount >= 0),
    CONSTRAINT ck_orders_status CHECK (status IN ('PENDING','PAID','PROCESSING','SHIPPED','DELIVERED','CANCELLED','REFUNDED'))
);

CREATE TABLE seller_order (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    seller_id UUID NOT NULL REFERENCES seller(id),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    subtotal NUMERIC(12,2) NOT NULL,
    shipping_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    commission_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    seller_amount NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (order_id,seller_id),
    UNIQUE (id,seller_id),
    CONSTRAINT ck_seller_order_subtotal CHECK (subtotal >= 0),
    CONSTRAINT ck_seller_order_shipping CHECK (shipping_amount >= 0),
    CONSTRAINT ck_seller_order_commission CHECK (commission_amount >= 0),
    CONSTRAINT ck_seller_order_seller_amount CHECK (seller_amount >= 0),
    CONSTRAINT ck_seller_order_status CHECK (status IN ('PENDING','PAID','PROCESSING','SHIPPED','DELIVERED','CANCELLED','REFUNDED'))
);

CREATE TABLE order_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_order_id UUID NOT NULL,
    product_id UUID NOT NULL,
    seller_id UUID NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (seller_order_id,seller_id) REFERENCES seller_order(id,seller_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id,seller_id) REFERENCES product(id,seller_id),
    CONSTRAINT ck_order_item_price CHECK (unit_price >= 0),
    CONSTRAINT ck_order_item_quantity CHECK (quantity > 0)
);

CREATE TABLE payment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    amount NUMERIC(12,2) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    transaction_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_payment_amount CHECK (amount >= 0),
    CONSTRAINT ck_payment_status CHECK (status IN ('PENDING','SUCCESS','FAILED','REFUNDED'))
);

CREATE TABLE review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES buyer(id),
    product_id UUID NOT NULL REFERENCES product(id),
    order_id UUID NOT NULL REFERENCES orders(id),
    rating SMALLINT NOT NULL,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (buyer_id,product_id,order_id),
    CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5)
);

CREATE INDEX idx_product_seller ON product(seller_id);
CREATE INDEX idx_product_category ON product(category_id);
CREATE INDEX idx_seller_order_seller ON seller_order(seller_id);
CREATE INDEX idx_seller_order_order ON seller_order(order_id);
CREATE INDEX idx_orders_buyer ON orders(buyer_id);
CREATE INDEX idx_order_item_seller_order ON order_item(seller_order_id);
CREATE INDEX idx_order_item_product ON order_item(product_id);
CREATE INDEX idx_review_product ON review(product_id);
CREATE INDEX idx_review_buyer ON review(buyer_id);
CREATE INDEX idx_category_parent ON category(parent_id);
CREATE INDEX ix_seller_status_history_seller_created ON seller_status_history(seller_id,created_at);
CREATE INDEX ix_seller_status_history_actor_account ON seller_status_history(actor_account_id);
CREATE INDEX ix_refresh_tokens_account_id ON refresh_tokens(account_id);
CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens(family_id);
CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens(expires_at);
