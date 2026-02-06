# Быстрые проверки миграции категорий

## 1) Запуск миграции через sqlite3
```bash
sqlite3 shop.db < migrations/2026_02_06_categories_by_business_type.sql
```

## 2) Проверка количества категорий по business_type
```bash
sqlite3 shop.db "SELECT business_type, COUNT(*) AS cnt FROM categories GROUP BY business_type ORDER BY business_type;"
```

## 3) Проверка обновления products.category_id
```bash
sqlite3 shop.db "SELECT COUNT(*) AS broken_refs FROM products p LEFT JOIN categories c ON c.id = p.category_id WHERE c.id IS NULL;"
```

Ожидаемо: `broken_refs = 0`.
