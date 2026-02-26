#!/usr/bin/env bash
set -e  # выходим при ошибке

# Проверяем, что мы в git-репозитории
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ Это не git-репозиторий. Перейди в папку проекта."
  exit 1
fi

# Определяем текущую ветку
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "======================================"
echo "Текущая ветка: $BRANCH"
echo "======================================"
echo
echo ">>> git status:"
git status
echo "======================================"

# Подтверждение пользователя
read -p "Продолжить коммит и пуш? (1 = да, 2 = нет): " ANSWER

if [[ "$ANSWER" != "1" ]]; then
  echo "Операция отменена."
  exit 0
fi

# Сообщение коммита
echo
read -p "Сообщение коммита (по умолчанию: \"Обновление файлов\"): " COMMIT_MSG
if [[ -z "$COMMIT_MSG" ]]; then
  COMMIT_MSG="Обновление файлов"
fi

echo
echo "Добавляем все изменения (git add -A)..."
git add -A

echo "Создаём коммит: \"$COMMIT_MSG\" ..."
if ! git commit -m "$COMMIT_MSG"; then
  echo "❗ Коммит не создан (скорее всего, нет изменений)."
  echo "Пуш отменён."
  exit 1
fi

echo
echo "Отправляем в удалённый репозиторий: origin $BRANCH ..."
git push origin "$BRANCH"

echo
echo "✅ Готово. Коммит отправлен в ветку: $BRANCH"
