#!/bin/bash
set -euo pipefail

DB_PATH="./shop.db"

if [ ! -f "$DB_PATH" ]; then
  echo "❌ База данных не найдена: $DB_PATH"
  exit 1
fi

# Проверим, что нужные таблицы есть
for t in shops shop_admins; do
  if ! sqlite3 "$DB_PATH" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='$t';" | grep -q 1; then
    echo "❌ В БД нет таблицы: $t"
    exit 1
  fi
done

echo "Выберите тип заведения:"
echo "1) Магазин"
echo "2) Ресторан"
read -p "> " TYPE_CHOICE

case "$TYPE_CHOICE" in
  1) BUSINESS_TYPE="shop" ;;
  2) BUSINESS_TYPE="restaurant" ;;
  *) echo "❌ Неверный выбор"; exit 1 ;;
esac

echo
echo "Список заведений ($BUSINESS_TYPE):"
sqlite3 -header -column "$DB_PATH" \
  "SELECT id, name, business_type, is_active FROM shops WHERE business_type='$BUSINESS_TYPE' ORDER BY id;"

echo
read -p "Введите ID заведения: " SHOP_ID
if ! [[ "$SHOP_ID" =~ ^[0-9]+$ ]]; then
  echo "❌ ID должен быть числом"
  exit 1
fi

# Проверим, что заведение существует и тип совпадает
EXISTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM shops WHERE id=$SHOP_ID AND business_type='$BUSINESS_TYPE';")
if [ "$EXISTS" != "1" ]; then
  echo "❌ Заведение не найдено или тип не совпадает (id=$SHOP_ID, type=$BUSINESS_TYPE)"
  exit 1
fi

echo
read -p "Введите Telegram user_id (число): " USER_ID
if ! [[ "$USER_ID" =~ ^[0-9]+$ ]]; then
  echo "❌ user_id должен быть числом"
  exit 1
fi

# Вставка. В твоей схеме PK(shop_id, user_id), поэтому используем INSERT OR IGNORE
sqlite3 "$DB_PATH" <<SQL
INSERT OR IGNORE INTO shop_admins (shop_id, user_id)
VALUES ($SHOP_ID, $USER_ID);
SQL

# Проверим, что запись есть
LINK=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM shop_admins WHERE shop_id=$SHOP_ID AND user_id=$USER_ID;")
if [ "$LINK" = "1" ]; then
  NAME=$(sqlite3 "$DB_PATH" "SELECT name FROM shops WHERE id=$SHOP_ID;")
  echo
  echo "✅ Пользователь назначен админом"
  echo "Заведение: $NAME (id=$SHOP_ID, type=$BUSINESS_TYPE)"
  echo "Telegram user_id: $USER_ID"
else
  echo "❌ Не удалось назначить админом. Проверь структуру таблицы shop_admins:"
  sqlite3 "$DB_PATH" "PRAGMA table_info(shop_admins);"
  exit 1
fi
