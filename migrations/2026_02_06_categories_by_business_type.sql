-- Миграция: категории становятся общими по business_type (shop/restaurant)
-- Важно: запускай на остановленных ботах!

PRAGMA foreign_keys = OFF;
BEGIN;

-- 1) Новая таблица категорий
CREATE TABLE IF NOT EXISTS categories_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_type TEXT CHECK (business_type IN ('shop','restaurant')) NOT NULL,
    name TEXT NOT NULL,
    name_norm TEXT DEFAULT '',
    sort INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

-- 2) Перенос + дедупликация по (business_type, name_norm)
INSERT INTO categories_new (business_type, name, name_norm, sort, is_active)
SELECT
  s.business_type AS business_type,
  MIN(c.name)     AS name,
  c.name_norm     AS name_norm,
  MIN(c.sort)     AS sort,
  MAX(c.is_active) AS is_active
FROM categories c
JOIN shops s ON s.id = c.shop_id
GROUP BY s.business_type, c.name_norm;

-- 3) Таблица сопоставления старых id категорий -> новых id категорий
CREATE TEMP TABLE cat_map AS
SELECT
  c.id AS old_id,
  cn.id AS new_id
FROM categories c
JOIN shops s ON s.id = c.shop_id
JOIN categories_new cn
  ON cn.business_type = s.business_type
 AND cn.name_norm = c.name_norm;

-- 4) Обновляем products.category_id на новые id
UPDATE products
SET category_id = (
  SELECT new_id FROM cat_map WHERE old_id = products.category_id
)
WHERE category_id IN (SELECT old_id FROM cat_map);

-- 5) Удаляем старую таблицу и индексы, переименовываем новую
DROP INDEX IF EXISTS idx_categories_shop;
DROP TABLE categories;
ALTER TABLE categories_new RENAME TO categories;

-- 6) Новые индексы
CREATE INDEX IF NOT EXISTS idx_categories_business ON categories(business_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_business_name_norm
  ON categories(business_type, name_norm);

COMMIT;
PRAGMA foreign_keys = ON;
