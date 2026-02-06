#!/bin/bash

echo "🔄 Обновляю все ветки из GitHub..."
git fetch --all --prune

git branch -r

echo ""
echo "Введите НАЗВАНИЕ удалённой ветки (как на GitHub):"
read REMOTE_BRANCH

# Проверка существования удалённой ветки
if ! git show-ref --verify --quiet "refs/remotes/origin/$REMOTE_BRANCH"; then
    echo "❌ Ветка origin/$REMOTE_BRANCH не найдена!"
    exit 1
fi

# Проверяем, существует ли локальная ветка
if git show-ref --verify --quiet "refs/heads/$REMOTE_BRANCH"; then
    echo "⚠️ Локальная ветка '$REMOTE_BRANCH' уже существует."
    echo "⏳ Переключаюсь на неё..."
    git checkout "$REMOTE_BRANCH"
    exit 0
fi

echo "📌 Создаю локальную ветку '$REMOTE_BRANCH' из origin/$REMOTE_BRANCH..."
git checkout -b "$REMOTE_BRANCH" "origin/$REMOTE_BRANCH"

if [ $? -eq 0 ]; then
    echo "✅ Готово! Вы переключены на ветку: $REMOTE_BRANCH"
else
    echo "❌ Ошибка при создании или переключении."
fi
