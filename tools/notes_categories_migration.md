# Миграция категорий по business_type

## Запуск миграции
```bash
sqlite3 shop.db < migrations/2026_02_06_categories_by_business_type.sql
```

## Проверка количества категорий по типам бизнеса
```bash
sqlite3 shop.db "SELECT business_type, COUNT(*) FROM categories GROUP BY business_type;"
```

## Проверка обновления category_id у продуктов
```bash
sqlite3 shop.db "SELECT id, shop_id, category_id FROM products LIMIT 20;"
```
