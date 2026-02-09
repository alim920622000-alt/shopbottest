#!/bin/bash
set -euo pipefail

DB="./shop.db"

if [ ! -f "$DB" ]; then
  echo "❌ Не найден файл БД: $DB"
  exit 1
fi

# Проверка таблиц
for t in shops categories; do
  ok=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='$t';")
  if [ "$ok" != "1" ]; then
    echo "❌ В БД нет таблицы: $t"
    exit 1
  fi
done

echo "Выберите тип заведения:"
echo "1) Ресторан"
read -r -p "> " TYPE_CHOICE

if [ "$TYPE_CHOICE" != "1" ]; then
  echo "❌ Этот скрипт сейчас добавляет категории только для ресторанов."
  exit 1
fi

echo
echo "Список ресторанов:"
sqlite3 -header -column "$DB" \
  "SELECT id, name, business_type, is_active FROM shops WHERE business_type='restaurant' ORDER BY id;"

echo
read -r -p "Введите ID ресторана: " RID
if ! [[ "$RID" =~ ^[0-9]+$ ]]; then
  echo "❌ ID должен быть числом"
  exit 1
fi

exists=$(sqlite3 "$DB" "SELECT COUNT(*) FROM shops WHERE id=$RID AND business_type='restaurant';")
if [ "$exists" != "1" ]; then
  echo "❌ Ресторан не найден (id=$RID) или это не restaurant"
  exit 1
fi

echo
read -r -p "Введите название категории: " CNAME

# Трим пробелов
CNAME="$(printf "%s" "$CNAME" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

if [ "${#CNAME}" -lt 2 ]; then
  echo "❌ Слишком короткое название (минимум 2 символа)"
  exit 1
fi

# Нормализация name_norm:
# - lower
# - убрать повторные пробелы
# - заменить знаки пунктуации на пробел
# - оставить кириллицу/латиницу/цифры и пробел
# - если вдруг стало пусто (не должно), fallback на lower+spaces
CNORM="$(python3 - <<'PY'
import sys, re

raw = sys.stdin.read()
raw = raw.strip()

low = raw.lower()
low = re.sub(r"\s+", " ", low).strip()

safe = re.sub(r"[^0-9a-zа-яё\s]+", " ", low, flags=re.IGNORECASE)
safe = re.sub(r"\s+", " ", safe).strip()

print(safe if safe else low)
PY
<<< "$CNAME")"

if [ -z "$CNORM" ] || [ "${#CNORM}" -lt 2 ]; then
  echo "❌ Не удалось сформировать корректный name_norm. Попробуй другое название."
  exit 1
fi

# Экранирование одинарных кавычек для SQL
CNAME_SQL="$(printf "%s" "$CNAME" | sed "s/'/''/g")"
CNORM_SQL="$(printf "%s" "$CNORM" | sed "s/'/''/g")"

# Проверим, что в таблице categories есть нужные колонки
col_ok=$(sqlite3 "$DB" "PRAGMA table_info(categories);" | awk -F'|' '{print $2}' | tr '\n' ' ')
case "$col_ok" in
  *"business_type"* ) ;;
  * )
    echo "❌ В таблице categories нет колонки business_type. Значит миграция ещё не применена."
    echo "PRAGMA table_info(categories):"
    sqlite3 "$DB" "PRAGMA table_info(categories);"
    exit 1
    ;;
esac

# Если категория уже есть — вывести и выйти
existing_id=$(sqlite3 "$DB" "SELECT id FROM categories WHERE business_type='restaurant' AND name_norm='$CNORM_SQL' LIMIT 1;")
if [ -n "$existing_id" ]; then
  echo
  echo "ℹ️ Категория уже существует."
  echo "ID: $existing_id"
  echo "Тип: restaurant"
  echo "Название: $CNAME"
  echo "name_norm: $CNORM"
  exit 0
fi

# Вставка
sqlite3 "$DB" <<SQL
INSERT INTO categories (business_type, name, name_norm, sort, is_active)
VALUES ('restaurant', '$CNAME_SQL', '$CNORM_SQL', 0, 1);
SQL

new_id=$(sqlite3 "$DB" "SELECT id FROM categories WHERE business_type='restaurant' AND name_norm='$CNORM_SQL' ORDER BY id DESC LIMIT 1;")
rname=$(sqlite3 "$DB" "SELECT name FROM shops WHERE id=$RID;")

echo
echo "✅ Категория добавлена"
echo "Ресторан: $rname (id=$RID)"
echo "ID категории: $new_id"
echo "Тип: restaurant"
echo "Название: $CNAME"
echo "name_norm: $CNORM"
