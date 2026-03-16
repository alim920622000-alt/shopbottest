#!/bin/bash
cd /home/ubuntu/bots/shop_bot_test
source venv/bin/activate
python3 -m app.admin_restaurant_main &
python3 -m app.admin_shop_main &
python3 -m app.client_main &
python3 -m app.courier_main &
echo "Боты запущены!"
