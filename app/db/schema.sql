PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    business_type TEXT CHECK (business_type IN ('shop','restaurant')) NOT NULL,
    phone TEXT,
    address TEXT,
    logo_url TEXT,
    about TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT CHECK (role IN ('client','admin','superadmin')) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shop_admins (
    shop_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'admin',
    PRIMARY KEY (shop_id, user_id),
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    name_norm TEXT DEFAULT '',
    sort INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    photo_url TEXT,
    name_norm TEXT DEFAULT '',
    keywords_norm TEXT DEFAULT '',
    unit TEXT DEFAULT 'шт',
    barcode TEXT DEFAULT '',
    sku TEXT,
    is_active INTEGER DEFAULT 1,
    updated_at DATETIME,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    client_user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_amount REAL NOT NULL,
    comment TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price_at_moment REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS client_profiles (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS search_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER,
    term TEXT NOT NULL,
    synonym TEXT NOT NULL,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS promotion_items (
    promo_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    PRIMARY KEY (promo_id, product_id),
    FOREIGN KEY (promo_id) REFERENCES promotions(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    sender_user_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL,
    message_text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_chat_reads (
    order_id INTEGER NOT NULL,
    viewer_role TEXT NOT NULL,
    viewer_user_id INTEGER NOT NULL,
    last_read_at DATETIME NOT NULL,
    PRIMARY KEY (order_id, viewer_role, viewer_user_id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_seen (
    order_id INTEGER NOT NULL,
    viewer_role TEXT NOT NULL,
    viewer_user_id INTEGER NOT NULL,
    seen_at DATETIME NOT NULL,
    PRIMARY KEY (order_id, viewer_role, viewer_user_id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_message_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    recipient_user_id INTEGER NOT NULL,
    recipient_kind TEXT NOT NULL,
    last_message_at DATETIME NOT NULL,
    last_message_preview TEXT NOT NULL,
    scheduled_at DATETIME NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    UNIQUE (order_id, recipient_user_id, recipient_kind)
);

CREATE TABLE IF NOT EXISTS ui_screens (
    bot_kind TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    screen_message_id INTEGER,
    updated_at TEXT,
    PRIMARY KEY (bot_kind, chat_id)
);

-- Индексы под частые выборки
-- CREATE INDEX IF NOT EXISTS idx_categories_shop ON categories(shop_id);
CREATE INDEX IF NOT EXISTS idx_products_shop ON products(shop_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_name_norm ON products(name_norm);
CREATE INDEX IF NOT EXISTS idx_products_keywords_norm ON products(keywords_norm);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_orders_shop_status ON orders(shop_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_user_id);
CREATE INDEX IF NOT EXISTS idx_shop_admins_user ON shop_admins(user_id);
CREATE INDEX IF NOT EXISTS idx_search_synonyms_term ON search_synonyms(term);
CREATE INDEX IF NOT EXISTS idx_promotions_shop ON promotions(shop_id);
CREATE INDEX IF NOT EXISTS idx_promo_items_promo ON promotion_items(promo_id);
CREATE INDEX IF NOT EXISTS idx_chat_order ON order_chat_messages(order_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_reads_viewer ON order_chat_reads(viewer_role, viewer_user_id);
CREATE INDEX IF NOT EXISTS idx_order_seen_viewer ON order_seen(viewer_role, viewer_user_id);
CREATE INDEX IF NOT EXISTS idx_chat_reminders_due ON chat_message_reminders(recipient_kind, status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_categories_business ON categories(business_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_business_name_norm ON categories(business_type, name_norm);
