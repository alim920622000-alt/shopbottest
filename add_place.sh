#!/bin/bash

DB_PATH="./shop.db"

if [ ! -f "$DB_PATH" ]; then
  echo "❌ База данных $DB_PATH не найдена"
  exit 1
fi

echo "Выберите тип заведения:"
echo "1) Магазин"
echo "2) Ресторан"
read -p "> " TYPE_CHOICE

case "$TYPE_CHOICE" in
  1) BUSINESS_TYPE="shop" ;;
  2) BUSINESS_TYPE="restaurant" ;;
  *)
    echo "❌ Неверный выбор"
    exit 1
    ;;
esac

read -p "Введите название заведения: " NAME

if [ -z "$NAME" ]; then
  echo "❌ Название не может быть пустым"
  exit 1
fi

SQL="
INSERT INTO shops (name, business_type)
VALUES ('$NAME', '$BUSINESS_TYPE');
"

sqlite3 "$DB_PATH" "$SQL"

if [ $? -eq 0 ]; then
  ID=$(sqlite3 "$DB_PATH" "SELECT id FROM shops ORDER BY id DESC LIMIT 1;")
  echo "✅ Заведение добавлено"
  echo "ID: $ID"
  echo "Тип: $BUSINESS_TYPE"
  echo "Название: $NAME"
else
  echo "❌ Ошибка при добавлении"
fi
