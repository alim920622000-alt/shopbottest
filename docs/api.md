# API документация: аутентификация

## POST /auth/login
Авторизация по `telegram_user_id`.

**Request JSON**
```json
{
  "telegram_user_id": 123456789
}
```

**Response JSON**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh>",
  "expires_in": 86400,
  "token_type": "bearer"
}
```

## POST /auth/refresh
Обновление access токена по refresh токену.

**Request JSON**
```json
{
  "refresh_token": "<refresh>"
}
```

**Response JSON**
```json
{
  "access_token": "<new_jwt>",
  "refresh_token": "<refresh>",
  "expires_in": 86400,
  "token_type": "bearer"
}
```

## POST /auth/logout
Отзыв refresh токена.

**Request JSON**
```json
{
  "refresh_token": "<refresh>"
}
```

**Response JSON**
```json
{
  "ok": true
}
```

## Ошибки
- Если refresh токен не существует / отозван / истёк — `401 Unauthorized`.
