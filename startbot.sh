#!/bin/bash

# Переходим в папку проекта
#cd ~/shop_bot

# Активируем виртуальное окружение
source venv/bin/activate

# Запускаем админ-бота ресторана
python3 -m app.admin_restaurant_main &

# Запускаем админ-бота магазина
python3 -m app.admin_shop_main &

# Запускаем клиентского бота
python3 -m app.client_main &
