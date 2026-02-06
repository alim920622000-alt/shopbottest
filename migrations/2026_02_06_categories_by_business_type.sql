PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE categories_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_type TEXT CHECK (business_type IN ('shop','restaurant')) NOT NULL,
    name TEXT NOT NULL,
    name_norm TEXT DEFAULT '',
    sort INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

INSERT INTO categories_new (business_type, name, name_norm, sort, is_active)
SELECT
    s.business_type,
    MIN(c.name) AS name,
    c.name_norm,
    MIN(c.sort) AS sort,
    MAX(c.is_active) AS is_active
FROM categories c
JOIN shops s ON s.id = c.shop_id
GROUP BY s.business_type, c.name_norm;

CREATE TEMP TABLE cat_map (
    old_id INTEGER PRIMARY KEY,
    new_id INTEGER NOT NULL
);

INSERT INTO cat_map (old_id, new_id)
SELECT
    c.id AS old_id,
    cn.id AS new_id
FROM categories c
JOIN shops s ON s.id = c.shop_id
JOIN categories_new cn
    ON cn.business_type = s.business_type
   AND cn.name_norm = c.name_norm;

UPDATE products
SET category_id = (
    SELECT cm.new_id
    FROM cat_map cm
    WHERE cm.old_id = products.category_id
)
WHERE category_id IN (SELECT old_id FROM cat_map);

DROP TABLE categories;
ALTER TABLE categories_new RENAME TO categories;

CREATE INDEX idx_categories_business ON categories(business_type);
CREATE UNIQUE INDEX uq_categories_business_name_norm ON categories(business_type, name_norm);

COMMIT;
PRAGMA foreign_keys = ON;
