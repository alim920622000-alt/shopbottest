# API сервер (FastAPI)

## Запуск

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Подготовить переменные окружения (можно через `.env`):

```env
DB_PATH=shop.db
API_JWT_SECRET=change_me_secret
API_PORT=8000
```

`DB_PATH` должен указывать на ту же SQLite базу, что используют боты.

3. Запустить сервер:

```bash
python -m app.api.main
```

После запуска доступно:
- OpenAPI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Примеры curl

### 1) Получить токен

```bash
curl -X POST "http://localhost:8000/auth/telegram" \
  -H "Content-Type: application/json" \
  -d '{"telegram_user_id":123456789}'
```

### 2) Получить список магазинов

```bash
curl "http://localhost:8000/catalog/merchants?type=shop" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 3) Получить категории магазина

```bash
curl "http://localhost:8000/catalog/1/categories?limit=20" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 4) Получить заказы текущего пользователя

```bash
curl "http://localhost:8000/orders?limit=20" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 5) Отправить сообщение в чат заказа

```bash
curl -X POST "http://localhost:8000/chats/1/messages" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"text":"Здравствуйте"}'
```
