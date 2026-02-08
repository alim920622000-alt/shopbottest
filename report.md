ubuntu@b3-8-eu-west-lz-zrh-a:~/bots/shop_bot_test$ git diff --name-status $A $B
M       app/db/database.py
M       app/db/schema.sql
M       app/handlers/fallback.py
M       app/handlers/start.py
M       app/handlers_admin_restaurant/extra.py
M       app/handlers_admin_restaurant/fallback.py
M       app/handlers_admin_restaurant/products.py
M       app/handlers_admin_restaurant/start.py
M       app/handlers_admin_shop/chat.py
M       app/handlers_admin_shop/extra.py
M       app/handlers_admin_shop/fallback.py
M       app/handlers_admin_shop/orders.py
M       app/handlers_admin_shop/products.py
M       app/handlers_admin_shop/start.py
M       app/handlers_client/cabinet.py
M       app/handlers_client/catalog.py
M       app/handlers_client/fallback.py
M       app/handlers_client/orders.py
M       app/handlers_client/start.py
A       app/i18n/client/ru.py
A       app/i18n/client/tj.py
A       app/i18n/client/uz.py
D       app/repositories/ui_screen_repo.py
M       app/services/chat_screen_controller.py
M       app/services/screen.py
D       app/utils/tg_safe.py
ubuntu@b3-8-eu-west-lz-zrh-a:~/bots/shop_bot_test$ git diff --stat $A $B
 app/db/database.py                        | 11 -------
 app/db/schema.sql                         |  8 -----
 app/handlers/fallback.py                  |  7 ++--
 app/handlers/start.py                     |  7 ++--
 app/handlers_admin_restaurant/extra.py    | 16 ++++------
 app/handlers_admin_restaurant/fallback.py | 22 ++++++-------
 app/handlers_admin_restaurant/products.py | 12 +++----
 app/handlers_admin_restaurant/start.py    | 34 ++++++--------------
 app/handlers_admin_shop/chat.py           | 12 +++----
 app/handlers_admin_shop/extra.py          |  4 +--
 app/handlers_admin_shop/fallback.py       | 22 ++++++-------
 app/handlers_admin_shop/orders.py         | 21 ++++--------
 app/handlers_admin_shop/products.py       | 24 +++++---------
 app/handlers_admin_shop/start.py          | 34 ++++++--------------
 app/handlers_client/cabinet.py            | 36 ++++-----------------
 app/handlers_client/catalog.py            | 14 ++++----
 app/handlers_client/fallback.py           | 12 +++++--
 app/handlers_client/orders.py             | 16 +++-------
 app/handlers_client/start.py              |  5 +--
 app/i18n/client/ru.py                     | 54 +++++++++++++++++++++++++++++++
 app/i18n/client/tj.py                     | 54 +++++++++++++++++++++++++++++++
 app/i18n/client/uz.py                     | 54 +++++++++++++++++++++++++++++++
 app/repositories/ui_screen_repo.py        | 51 -----------------------------
 app/services/chat_screen_controller.py    | 59 ++++++++--------------------------
 app/services/screen.py                    | 87 +++++++++++++++++---------------------------------
 app/utils/tg_safe.py                      | 22 -------------
 26 files changed, 312 insertions(+), 386 deletions(-)
ubuntu@b3-8-eu-west-lz-zrh-a:~/bots/shop_bot_test$ git diff --summary $A $B
 create mode 100644 app/i18n/client/ru.py
 create mode 100644 app/i18n/client/tj.py
 create mode 100644 app/i18n/client/uz.py
 delete mode 100644 app/repositories/ui_screen_repo.py
 delete mode 100644 app/utils/tg_safe.py
ubuntu@b3-8-eu-west-lz-zrh-a:~/bots/shop_bot_test$ git diff --dirstat=files,0 $A $B
   7.6% app/db/
   7.6% app/handlers/
  15.3% app/handlers_admin_restaurant/
  23.0% app/handlers_admin_shop/
  19.2% app/handlers_client/
  11.5% app/i18n/client/
   3.8% app/repositories/
   7.6% app/services/
   3.8% app/utils/
ubuntu@b3-8-eu-west-lz-zrh-a:~/bots/shop_bot_test$ git diff $A $B
diff --git a/app/db/database.py b/app/db/database.py
index 2232d72..8af3b95 100644
--- a/app/db/database.py
+++ b/app/db/database.py
@@ -143,17 +143,6 @@ class Database:
             )
             """
         )
-        await connection.execute(
-            """
-            CREATE TABLE IF NOT EXISTS ui_screens (
-                bot_kind TEXT NOT NULL,
-                chat_id INTEGER NOT NULL,
-                screen_message_id INTEGER,
-                updated_at TEXT,
-                PRIMARY KEY (bot_kind, chat_id)
-            )
-            """
-        )

         await connection.execute("CREATE INDEX IF NOT EXISTS idx_products_name_norm ON products(name_norm);")
         await connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku ON products(sku);")
diff --git a/app/db/schema.sql b/app/db/schema.sql
index 3dcf618..35b23cf 100644
--- a/app/db/schema.sql
+++ b/app/db/schema.sql
@@ -126,14 +126,6 @@ CREATE TABLE IF NOT EXISTS order_chat_messages (
     FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
 );

-CREATE TABLE IF NOT EXISTS ui_screens (
-    bot_kind TEXT NOT NULL,
-    chat_id INTEGER NOT NULL,
-    screen_message_id INTEGER,
-    updated_at TEXT,
-    PRIMARY KEY (bot_kind, chat_id)
-);
-
 -- Индексы под частые выборки
 -- CREATE INDEX IF NOT EXISTS idx_categories_shop ON categories(shop_id);
 CREATE INDEX IF NOT EXISTS idx_products_shop ON products(shop_id);
diff --git a/app/handlers/fallback.py b/app/handlers/fallback.py
index eb73a9c..7d195a6 100644
--- a/app/handlers/fallback.py
+++ b/app/handlers/fallback.py
@@ -4,13 +4,12 @@ from aiogram.fsm.context import FSMContext

 from app.keyboards import kb_main
 from app.services.screen import delete_screen, show_main_menu
-from app.db.database import Database

 router = Router()


 @router.message(F.text)
-async def fallback_handler(message: Message, state: FSMContext, auth_role: str, db: Database):
+async def fallback_handler(message: Message, state: FSMContext, auth_role: str):
     if await state.get_state() is not None:
         return
     if message.text and message.text.startswith("/"):
@@ -18,6 +17,6 @@ async def fallback_handler(message: Message, state: FSMContext, auth_role: str,
     if auth_role == "none":
         await message.answer("Доступ запрещён. Ваш user_id не добавлен в список администраторов.")
         return
-    await delete_screen(message.bot, message.chat.id, state, db, "admin_shop")
+    await delete_screen(message.bot, message.chat.id, state)
     await message.answer("Я не понял команду. Используйте меню ниже.")
-    await show_main_menu(message.bot, message.chat.id, state, db, "admin_shop", "Главное меню:", kb_main())
+    await show_main_menu(message.bot, message.chat.id, state, "Главное меню:", kb_main())
diff --git a/app/handlers/start.py b/app/handlers/start.py
index 682b59a..10b060d 100644
--- a/app/handlers/start.py
+++ b/app/handlers/start.py
@@ -5,16 +5,15 @@ from aiogram.fsm.context import FSMContext
 from app.states import MenuStates
 from app.keyboards import kb_main
 from app.services.screen import clear_state_keep_screen, show_main_menu
-from app.db.database import Database

 router = Router()

 @router.message(CommandStart())
-async def start_cmd(message: Message, state: FSMContext, auth_role: str, db: Database):
+async def start_cmd(message: Message, state: FSMContext, auth_role: str):
     if auth_role == "none":
         await message.answer("Доступ запрещён. Ваш user_id не добавлен в список администраторов.")
         return

-    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+    await clear_state_keep_screen(state)
     await state.set_state(MenuStates.main)
-    await show_main_menu(message.bot, message.chat.id, state, db, "admin_shop", "Главное меню:", kb_main())
+    await show_main_menu(message.bot, message.chat.id, state, "Главное меню:", kb_main())
diff --git a/app/handlers_admin_restaurant/extra.py b/app/handlers_admin_restaurant/extra.py
index 5f358ff..b3db186 100644
--- a/app/handlers_admin_restaurant/extra.py
+++ b/app/handlers_admin_restaurant/extra.py
@@ -155,14 +155,12 @@ async def promo_add_description(message: Message, state: FSMContext, db: Databas
         return
     repo = PromotionsRepo(db)
     await repo.create(ids[0], title=title, description=desc)
-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
+    await clear_state_keep_screen(state)
     await message.answer("Акция добавлена ✅")
     await show_main_menu(
         message.bot,
         message.chat.id,
         state,
-        db,
-        "admin_restaurant",
         "Админ-меню ресторана:",
         kb_admin_main(),
     )
@@ -287,7 +285,7 @@ async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext):
     if not await is_restaurant_admin(db, cq.from_user.id):
         await cq.answer("Нет доступа", show_alert=True)
         return
-    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
+    await clear_state_keep_screen(state)
     ids = await get_admin_restaurant_ids(db, cq.from_user.id)
     if not ids:
         await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
@@ -331,7 +329,7 @@ async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         return
     await state.set_state(RestaurantChatStates.active)
     await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
-    await set_screen_message_id(state, db, "admin_restaurant", cq.message.chat.id, cq.message.message_id)
+    await set_screen_message_id(state, cq.message.message_id)
     await render_chat(cq, db, order_id, page=10**9)
     await cq.answer()

@@ -350,7 +348,7 @@ async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         await cq.answer("Чат недоступен.", show_alert=True)
         return
     await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
-    await set_screen_message_id(state, db, "admin_restaurant", cq.message.chat.id, cq.message.message_id)
+    await set_screen_message_id(state, cq.message.message_id)
     await render_chat(cq, db, order_id, page=page)
     await cq.answer()

@@ -396,12 +394,12 @@ async def send_chat_message(message: Message, state: FSMContext, db: Database):
                 message_id=int(chat_message_id),
                 reply_markup=kb,
             )
-            await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, int(chat_message_id))
+            await set_screen_message_id(state, int(chat_message_id))
         except Exception:
             new_message = await message.answer(text, reply_markup=kb)
             await state.update_data(chat_message_id=new_message.message_id)
-            await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, new_message.message_id)
+            await set_screen_message_id(state, new_message.message_id)
     else:
         new_message = await message.answer(text, reply_markup=kb)
         await state.update_data(chat_message_id=new_message.message_id)
-        await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, new_message.message_id)
+        await set_screen_message_id(state, new_message.message_id)
diff --git a/app/handlers_admin_restaurant/fallback.py b/app/handlers_admin_restaurant/fallback.py
index 2d243d1..ae9832f 100644
--- a/app/handlers_admin_restaurant/fallback.py
+++ b/app/handlers_admin_restaurant/fallback.py
@@ -5,15 +5,13 @@ from aiogram.fsm.context import FSMContext
 from app.db.database import Database
 from app.handlers_admin_restaurant.start import kb_admin_main
 from app.handlers_admin_restaurant.utils import is_restaurant_admin
-from app.services.chat_screen_controller import ChatScreenController
+from app.services.screen import delete_screen, show_main_menu

 router = Router()


 @router.message(F.text)
 async def fallback_handler(message: Message, state: FSMContext, db: Database):
-    if message.via_bot is not None:
-        return
     if await state.get_state() is not None:
         return
     if message.text and message.text.startswith("/"):
@@ -21,14 +19,12 @@ async def fallback_handler(message: Message, state: FSMContext, db: Database):
     if not await is_restaurant_admin(db, message.from_user.id):
         await message.answer("Нет доступа. Ваш user_id не назначен админом ресторана.")
         return
-    controller = ChatScreenController(
-        bot=message.bot,
-        chat_id=message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню ресторана:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_restaurant",
-    )
-    await controller.delete_user_message(message)
+    await delete_screen(message.bot, message.chat.id, state)
     await message.answer("Я не понял команду. Используйте меню ниже.")
-    await controller.refresh()
+    await show_main_menu(
+        message.bot,
+        message.chat.id,
+        state,
+        "Админ-меню ресторана:",
+        kb_admin_main(),
+    )
diff --git a/app/handlers_admin_restaurant/products.py b/app/handlers_admin_restaurant/products.py
index 97e3827..c6f8b4a 100644
--- a/app/handlers_admin_restaurant/products.py
+++ b/app/handlers_admin_restaurant/products.py
@@ -243,7 +243,7 @@ async def add_product_desc(message: Message, state: FSMContext, db: Database):
         await conn.commit()

     # ВАЖНО: очищаем FSM, чтобы не спрашивало описание снова
-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
+    await clear_state_keep_screen(state)

     # Чтобы кнопки были ВНИЗУ, делаем новый список сообщением (а не edit старого)
     prod = ProductsRepo(db)
@@ -339,7 +339,7 @@ async def edit_name_apply(message: Message, state: FSMContext, db: Database):
     prod = ProductsRepo(db)
     await prod.update(product_id, name=name)

-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
+    await clear_state_keep_screen(state)

     await render_product_card_edit(
         message.bot,
@@ -378,7 +378,7 @@ async def edit_price_apply(message: Message, state: FSMContext, db: Database):
     prod = ProductsRepo(db)
     await prod.update(product_id, price=price)

-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
+    await clear_state_keep_screen(state)

     await render_product_card_edit(
         message.bot,
@@ -414,7 +414,7 @@ async def edit_desc_apply(message: Message, state: FSMContext, db: Database):
     prod = ProductsRepo(db)
     await prod.update(product_id, description=desc)

-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
+    await clear_state_keep_screen(state)

     await render_product_card_edit(
         message.bot,
@@ -502,9 +502,9 @@ async def open_product(cq: CallbackQuery, db: Database):


 @router.callback_query(F.data == "r:cancel")
-async def cancel_fsm(cq: CallbackQuery, state: FSMContext, db: Database):
+async def cancel_fsm(cq: CallbackQuery, state: FSMContext):
     data = await state.get_data()
-    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
+    await clear_state_keep_screen(state)

     # если знаем, откуда пришли — возвращаем в список позиций категории
     restaurant_id = data.get("restaurant_id")
diff --git a/app/handlers_admin_restaurant/start.py b/app/handlers_admin_restaurant/start.py
index ed75e90..9fe9c0a 100644
--- a/app/handlers_admin_restaurant/start.py
+++ b/app/handlers_admin_restaurant/start.py
@@ -5,8 +5,7 @@ from aiogram.fsm.context import FSMContext

 from app.db.database import Database
 from app.handlers_admin_restaurant.utils import is_restaurant_admin
-from app.services.screen import clear_state_keep_screen
-from app.services.chat_screen_controller import ChatScreenController
+from app.services.screen import clear_state_keep_screen, show_main_menu

 router = Router()

@@ -27,31 +26,18 @@ async def start_cmd(message: Message, db: Database, state: FSMContext):
     if not await is_restaurant_admin(db, message.from_user.id):
         await message.answer("Нет доступа. Ваш user_id не назначен админом ресторана.")
         return
-    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
-    controller = ChatScreenController(
-        bot=message.bot,
-        chat_id=message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню ресторана:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_restaurant",
+    await clear_state_keep_screen(state)
+    await show_main_menu(
+        message.bot,
+        message.chat.id,
+        state,
+        "Админ-меню ресторана:",
+        kb_admin_main(),
     )
-    await controller.delete_user_message(message)
-    await controller.delete_screen()
-    await controller.refresh()


 @router.callback_query(F.data == "r:home")
 async def home(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
-    controller = ChatScreenController(
-        bot=cq.bot,
-        chat_id=cq.message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню ресторана:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_restaurant",
-    )
-    await controller.delete_screen()
-    await controller.refresh()
+    await clear_state_keep_screen(state)
+    await cq.message.edit_text("Админ-меню ресторана:", reply_markup=kb_admin_main())
     await cq.answer()
diff --git a/app/handlers_admin_shop/chat.py b/app/handlers_admin_shop/chat.py
index c0a6eb8..74b7c4a 100644
--- a/app/handlers_admin_shop/chat.py
+++ b/app/handlers_admin_shop/chat.py
@@ -45,7 +45,7 @@ async def list_chats(cq: CallbackQuery, db: Database, state: FSMContext):
         await cq.answer("Нет доступа", show_alert=True)
         return

-    await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
+    await clear_state_keep_screen(state)
     shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
     if not shop_ids:
         await cq.message.edit_text("Нет доступа.", reply_markup=kb_admin_main())
@@ -92,7 +92,7 @@ async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         return
     await state.set_state(AdminShopChatStates.active)
     await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
-    await set_screen_message_id(state, db, "admin_shop", cq.message.chat.id, cq.message.message_id)
+    await set_screen_message_id(state, cq.message.message_id)
     await render_chat(cq, db, order_id, page=10**9)
     await cq.answer()

@@ -111,7 +111,7 @@ async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         await cq.answer("Чат недоступен.", show_alert=True)
         return
     await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
-    await set_screen_message_id(state, db, "admin_shop", cq.message.chat.id, cq.message.message_id)
+    await set_screen_message_id(state, cq.message.message_id)
     await render_chat(cq, db, order_id, page=page)
     await cq.answer()

@@ -161,12 +161,12 @@ async def send_chat_message(message: Message, state: FSMContext, db: Database):
                 message_id=int(chat_message_id),
                 reply_markup=kb,
             )
-            await set_screen_message_id(state, db, "admin_shop", message.chat.id, int(chat_message_id))
+            await set_screen_message_id(state, int(chat_message_id))
         except Exception:
             new_message = await message.answer(text, reply_markup=kb)
             await state.update_data(chat_message_id=new_message.message_id)
-            await set_screen_message_id(state, db, "admin_shop", message.chat.id, new_message.message_id)
+            await set_screen_message_id(state, new_message.message_id)
     else:
         new_message = await message.answer(text, reply_markup=kb)
         await state.update_data(chat_message_id=new_message.message_id)
-        await set_screen_message_id(state, db, "admin_shop", message.chat.id, new_message.message_id)
+        await set_screen_message_id(state, new_message.message_id)
diff --git a/app/handlers_admin_shop/extra.py b/app/handlers_admin_shop/extra.py
index f70d4b3..45f526b 100644
--- a/app/handlers_admin_shop/extra.py
+++ b/app/handlers_admin_shop/extra.py
@@ -153,14 +153,12 @@ async def promo_add_description(message: Message, state: FSMContext, db: Databas
         return
     repo = PromotionsRepo(db)
     await repo.create(shop_ids[0], title=title, description=desc)
-    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+    await clear_state_keep_screen(state)
     await message.answer("Акция добавлена ✅")
     await show_main_menu(
         message.bot,
         message.chat.id,
         state,
-        db,
-        "admin_shop",
         "Админ-меню магазина:",
         kb_admin_main(),
     )
diff --git a/app/handlers_admin_shop/fallback.py b/app/handlers_admin_shop/fallback.py
index 82f9b80..5a0da37 100644
--- a/app/handlers_admin_shop/fallback.py
+++ b/app/handlers_admin_shop/fallback.py
@@ -5,15 +5,13 @@ from aiogram.fsm.context import FSMContext
 from app.db.database import Database
 from app.handlers_admin_shop.start import kb_admin_main
 from app.handlers_admin_shop.utils import is_shop_admin
-from app.services.chat_screen_controller import ChatScreenController
+from app.services.screen import delete_screen, show_main_menu

 router = Router()


 @router.message(F.text)
 async def fallback_handler(message: Message, state: FSMContext, db: Database):
-    if message.via_bot is not None:
-        return
     if await state.get_state() is not None:
         return
     if message.text and message.text.startswith("/"):
@@ -21,14 +19,12 @@ async def fallback_handler(message: Message, state: FSMContext, db: Database):
     if not await is_shop_admin(db, message.from_user.id):
         await message.answer("Нет доступа. Ваш user_id не назначен админом магазина.")
         return
-    controller = ChatScreenController(
-        bot=message.bot,
-        chat_id=message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню магазина:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_shop",
-    )
-    await controller.delete_user_message(message)
+    await delete_screen(message.bot, message.chat.id, state)
     await message.answer("Я не понял команду. Используйте меню ниже.")
-    await controller.refresh()
+    await show_main_menu(
+        message.bot,
+        message.chat.id,
+        state,
+        "Админ-меню магазина:",
+        kb_admin_main(),
+    )
diff --git a/app/handlers_admin_shop/orders.py b/app/handlers_admin_shop/orders.py
index 5063124..adf653f 100644
--- a/app/handlers_admin_shop/orders.py
+++ b/app/handlers_admin_shop/orders.py
@@ -1,5 +1,3 @@
-from aiogram.exceptions import TelegramBadRequest
-from app.utils.tg_safe import safe_edit_text
 from aiogram import Router, F
 from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
 from app.handlers_admin_shop.start import kb_admin_main  # добавь импорт
@@ -45,8 +43,7 @@ def kb_order_card(order_id: int) -> InlineKeyboardMarkup:

 @router.callback_query(F.data == "a:home")
 async def admin_home(cq: CallbackQuery, db: Database):
-    await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())
-
+    await cq.message.edit_text("Админ-меню магазина:", reply_markup=kb_admin_main())
     await cq.answer()


@@ -54,7 +51,7 @@ async def admin_home(cq: CallbackQuery, db: Database):
 async def list_orders(cq: CallbackQuery, db: Database):
     shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
     if not shop_ids:
-        await safe_edit_text(cq.message, "Нет доступа.", reply_markup=kb_back_admin())
+        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_admin())
         await cq.answer()
         return

@@ -64,11 +61,7 @@ async def list_orders(cq: CallbackQuery, db: Database):
     orders = OrdersRepo(db)
     rows = await orders.list_current_for_shop(shop_id=shop_id, statuses=["new", "preparing", "ready"])
     if not rows:
-        await safe_edit_text(
-            cq.message,
-            f"Текущие заказы (shop_id={shop_id}):",
-            reply_markup=kb_orders_list(order_ids),
-        )
+        await cq.message.edit_text("Текущих заказов нет.", reply_markup=kb_back_admin())
         await cq.answer()
         return

@@ -84,7 +77,7 @@ async def order_card(cq: CallbackQuery, db: Database):
     orders = OrdersRepo(db)
     o = await orders.get_order(order_id)
     if not o:
-        await safe_edit_text(cq.message, "Заказ не найден.", reply_markup=kb_back_admin())
+        await cq.message.edit_text("Заказ не найден.", reply_markup=kb_back_admin())
         await cq.answer()
         return

@@ -93,7 +86,7 @@ async def order_card(cq: CallbackQuery, db: Database):
     for it in items:
         lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

-    await safe_edit_text(cq.message, "\n".join(lines), reply_markup=kb_order_card(order_id))
+    await cq.message.edit_text("\n".join(lines), reply_markup=kb_order_card(order_id))
     await cq.answer()


@@ -113,10 +106,10 @@ async def set_status(cq: CallbackQuery, db: Database):
     lines = [f"Заказ #{o['id']}", f"Статус: {o['status']}", f"Сумма: {o['total_amount']}", "", "Состав:"]
     for it in items:
         lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
-    await safe_edit_text(cq.message, "\n".join(lines), reply_markup=kb_order_card(order_id))
+    await cq.message.edit_text("\n".join(lines), reply_markup=kb_order_card(order_id))


 @router.callback_query(F.data == "a:back:main")
 async def back_main(cq: CallbackQuery):
-    await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())
+    await cq.message.edit_text("Админ-меню магазина:", reply_markup=kb_admin_main())
     await cq.answer()
diff --git a/app/handlers_admin_shop/products.py b/app/handlers_admin_shop/products.py
index 46d56e7..87992a3 100644
--- a/app/handlers_admin_shop/products.py
+++ b/app/handlers_admin_shop/products.py
@@ -184,19 +184,17 @@ async def add_category_save(message: Message, state: FSMContext, db: Database):

     if not is_superadmin(message.from_user.id):
         await message.answer("Только супер-админ может добавлять категории.")
-        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+        await clear_state_keep_screen(state)
         return

     shop_id = await _get_shop_id_for_admin(db, message.from_user.id)
     if not shop_id:
         await message.answer("Нет привязанного магазина.")
-        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+        await clear_state_keep_screen(state)
         await show_main_menu(
             message.bot,
             message.chat.id,
             state,
-            db,
-            "admin_shop",
             "Админ-меню магазина:",
             kb_admin_main(),
         )
@@ -209,14 +207,12 @@ async def add_category_save(message: Message, state: FSMContext, db: Database):

     await CategoriesRepo(db).create(shop_id=shop_id, name=name, sort=0)

-    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+    await clear_state_keep_screen(state)
     await message.answer("Категория добавлена ✅")
     await show_main_menu(
         message.bot,
         message.chat.id,
         state,
-        db,
-        "admin_shop",
         "Админ-меню магазина:",
         kb_admin_main(),
     )
@@ -277,13 +273,11 @@ async def add_product_save(message: Message, state: FSMContext, db: Database):
     shop_id = await _get_shop_id_for_admin(db, message.from_user.id)
     if not shop_id:
         await message.answer("Нет привязанного магазина.")
-        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+        await clear_state_keep_screen(state)
         await show_main_menu(
             message.bot,
             message.chat.id,
             state,
-            db,
-            "admin_shop",
             "Админ-меню магазина:",
             kb_admin_main(),
         )
@@ -307,14 +301,12 @@ async def add_product_save(message: Message, state: FSMContext, db: Database):
     repo = ProductsRepo(db)
     await repo.create(shop_id=shop_id, category_id=cat_id, name=name, price=price)

-    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
+    await clear_state_keep_screen(state)
     await message.answer("Товар добавлен ✅")
     await show_main_menu(
         message.bot,
         message.chat.id,
         state,
-        db,
-        "admin_shop",
         "Админ-меню магазина:",
         kb_admin_main(),
     )
@@ -505,7 +497,7 @@ async def bulk_import_prompt(cq: CallbackQuery, state: FSMContext, db: Database)
                     )
         except Exception:
             logger.error("Bulk import failed for admin %s", cq.from_user.id, exc_info=True)
-            await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
+            await clear_state_keep_screen(state)
             await cq.message.edit_text(
                 "Ошибка во время импорта. Проверьте файл и попробуйте снова.",
                 reply_markup=kb_admin_main(),
@@ -526,14 +518,14 @@ async def bulk_import_prompt(cq: CallbackQuery, state: FSMContext, db: Database)
             if len(errors) > 5:
                 summary_lines.append(f"... и ещё {len(errors) - 5} ошибок")

-        await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
+        await clear_state_keep_screen(state)
         await cq.message.edit_text("\n".join(summary_lines), reply_markup=kb_admin_main())
         await cq.answer()
         return

     if action == "cancel":
         logger.info("Bulk import canceled by admin %s", cq.from_user.id)
-        await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
+        await clear_state_keep_screen(state)
         await cq.message.edit_text("Импорт отменён.", reply_markup=kb_admin_main())
         await cq.answer()
         return
diff --git a/app/handlers_admin_shop/start.py b/app/handlers_admin_shop/start.py
index 4e5fdbb..646f91a 100644
--- a/app/handlers_admin_shop/start.py
+++ b/app/handlers_admin_shop/start.py
@@ -5,8 +5,7 @@ from aiogram.fsm.context import FSMContext

 from app.db.database import Database
 from app.handlers_admin_shop.utils import is_shop_admin
-from app.services.screen import clear_state_keep_screen
-from app.services.chat_screen_controller import ChatScreenController
+from app.services.screen import clear_state_keep_screen, show_main_menu

 router = Router()

@@ -28,32 +27,19 @@ async def start_cmd(message: Message, db: Database, state: FSMContext):
         await message.answer("Нет доступа. Ваш user_id не назначен админом магазина.")
         return

-    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
-    controller = ChatScreenController(
-        bot=message.bot,
-        chat_id=message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню магазина:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_shop",
+    await clear_state_keep_screen(state)
+    await show_main_menu(
+        message.bot,
+        message.chat.id,
+        state,
+        "Админ-меню магазина:",
+        kb_admin_main(),
     )
-    await controller.delete_user_message(message)
-    await controller.delete_screen()
-    await controller.refresh()


 @router.callback_query(F.data == "a:home")
 async def home(cq, db: Database, state: FSMContext):
     # Быстрый возврат в главное меню
-    await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
-    controller = ChatScreenController(
-        bot=cq.bot,
-        chat_id=cq.message.chat.id,
-        state=state,
-        render=lambda: ("Админ-меню магазина:", kb_admin_main()),
-        db=db,
-        bot_kind="admin_shop",
-    )
-    await controller.delete_screen()
-    await controller.refresh()
+    await clear_state_keep_screen(state)
+    await cq.message.edit_text("Админ-меню магазина:", reply_markup=kb_admin_main())
     await cq.answer()
diff --git a/app/handlers_client/cabinet.py b/app/handlers_client/cabinet.py
index 2e7883c..b80bcc8 100644
--- a/app/handlers_client/cabinet.py
+++ b/app/handlers_client/cabinet.py
@@ -78,19 +78,11 @@ async def save_full_name(message: Message, state: FSMContext, db: Database):
         return
     repo = ClientProfilesRepo(db)
     await repo.upsert(message.from_user.id, full_name=name)
-    await clear_state_keep_screen(state, db, "client", message.chat.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=message.from_user.id)
     await remember_client_screen(state, "main", {})
     await message.answer("ФИО сохранено.")
-    await show_main_menu(
-        message.bot,
-        message.chat.id,
-        state,
-        db,
-        "client",
-        "Выберите раздел:",
-        kb_client_main(),
-    )
+    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())


 @router.message(CabinetStates.edit_phone)
@@ -101,19 +93,11 @@ async def save_phone(message: Message, state: FSMContext, db: Database):
         return
     repo = ClientProfilesRepo(db)
     await repo.upsert(message.from_user.id, phone=phone)
-    await clear_state_keep_screen(state, db, "client", message.chat.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=message.from_user.id)
     await remember_client_screen(state, "main", {})
     await message.answer("Телефон сохранён.")
-    await show_main_menu(
-        message.bot,
-        message.chat.id,
-        state,
-        db,
-        "client",
-        "Выберите раздел:",
-        kb_client_main(),
-    )
+    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())


 @router.message(CabinetStates.edit_address)
@@ -124,16 +108,8 @@ async def save_address(message: Message, state: FSMContext, db: Database):
         return
     repo = ClientProfilesRepo(db)
     await repo.upsert(message.from_user.id, address=address)
-    await clear_state_keep_screen(state, db, "client", message.chat.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=message.from_user.id)
     await remember_client_screen(state, "main", {})
     await message.answer("Адрес сохранён.")
-    await show_main_menu(
-        message.bot,
-        message.chat.id,
-        state,
-        db,
-        "client",
-        "Выберите раздел:",
-        kb_client_main(),
-    )
+    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())
diff --git a/app/handlers_client/catalog.py b/app/handlers_client/catalog.py
index 6e2039a..6c3ffcd 100644
--- a/app/handlers_client/catalog.py
+++ b/app/handlers_client/catalog.py
@@ -98,7 +98,7 @@ async def open_product_from_inline_sku(message: Message, db: Database, state: FS
         return

     # Удаляем только текущее экранное сообщение бота. Inline-сообщение не трогаем.
-    await delete_screen(message.bot, message.chat.id, state, db, "client")
+    await delete_screen(message.bot, message.chat.id, state)

     text = _build_product_card_text(product)
     sent = await message.answer(
@@ -109,7 +109,7 @@ async def open_product_from_inline_sku(message: Message, db: Database, state: FS
             sku=sku,
         ),
     )
-    await set_screen_message_id(state, db, "client", message.chat.id, sent.message_id)
+    await set_screen_message_id(state, sent.message_id)
     await state.update_data(
         last_kind="shop",
         last_view={
@@ -144,16 +144,16 @@ async def list_shops(cq: CallbackQuery, db: Database, state: FSMContext):


 @router.callback_query(F.data == "c:home")
-async def client_home(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+async def client_home(cq: CallbackQuery, state: FSMContext):
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "main", {})
     await cq.message.edit_text("Выберите раздел:", reply_markup=kb_client_main())
     await cq.answer()

 @router.callback_query(F.data == "c:order_menu")
-async def order_menu(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+async def order_menu(cq: CallbackQuery, state: FSMContext):
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "order_menu", {})
     await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
@@ -471,7 +471,7 @@ async def back(cq: CallbackQuery, db: Database, state: FSMContext):
         await cq.answer()
         return

-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+    await clear_state_keep_screen(state)

     if target == "main":
         await cq.message.edit_text("Выберите раздел:", reply_markup=kb_client_main())
diff --git a/app/handlers_client/fallback.py b/app/handlers_client/fallback.py
index f59ed24..2350273 100644
--- a/app/handlers_client/fallback.py
+++ b/app/handlers_client/fallback.py
@@ -1,3 +1,5 @@
+import asyncio
+
 from aiogram import Router, F
 from aiogram.types import Message
 from aiogram.fsm.context import FSMContext
@@ -22,10 +24,14 @@ async def fallback_handler(message: Message, state: FSMContext, db: Database):
         chat_id=message.chat.id,
         state=state,
         render=lambda: render_client_screen(db, state),
-        db=db,
-        bot_kind="client",
     )

     await controller.delete_user_message(message)
-    await message.answer("Я не понял команду. Используйте меню ниже.")
+    notice = await message.answer("Я не понял команду. Используйте меню ниже.")
     await controller.refresh()
+
+    try:
+        await asyncio.sleep(2)
+        await message.bot.delete_message(message.chat.id, notice.message_id)
+    except Exception:
+        pass
diff --git a/app/handlers_client/orders.py b/app/handlers_client/orders.py
index 53348f9..fbd1c99 100644
--- a/app/handlers_client/orders.py
+++ b/app/handlers_client/orders.py
@@ -18,7 +18,7 @@ from app.services.chat_ui import (
     calc_total_pages,
     remember_client_hint,
 )
-from app.services.screen import clear_state_keep_screen
+from app.services.screen import clear_state_keep_screen, set_screen_message_id
 from app.services.chat_screen_controller import ChatScreenController
 from app.services.client_ui_state import remember_client_screen

@@ -81,7 +81,7 @@ def make_chat_render_fn(db: Database, state: FSMContext):

 @router.callback_query(F.data == "c:orders")
 async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "orders", {})
     orders = OrdersRepo(db)
@@ -98,7 +98,7 @@ async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):

 @router.callback_query(F.data == "c:history")
 async def list_history(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "history", {})
     orders = OrdersRepo(db)
@@ -115,7 +115,7 @@ async def list_history(cq: CallbackQuery, db: Database, state: FSMContext):

 @router.callback_query(F.data.startswith("c:order:"))
 async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+    await clear_state_keep_screen(state)
     order_id = int(cq.data.split(":")[2])
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "order_card", {"order_id": order_id})
@@ -149,7 +149,7 @@ async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):

 @router.callback_query(F.data == "c:chat")
 async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext):
-    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
+    await clear_state_keep_screen(state)
     await state.update_data(user_id=cq.from_user.id)
     await remember_client_screen(state, "chat_list", {})
     chats = ChatRepo(db)
@@ -215,8 +215,6 @@ async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         chat_id=cq.from_user.id,
         state=state,
         render=make_chat_render_fn(db, state),
-        db=db,
-        bot_kind="client",
     )
     await controller.refresh()
     await cq.answer()
@@ -243,8 +241,6 @@ async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
         chat_id=cq.from_user.id,
         state=state,
         render=make_chat_render_fn(db, state),
-        db=db,
-        bot_kind="client",
     )
     await controller.refresh()
     await cq.answer()
@@ -288,7 +284,5 @@ async def send_chat_message(message: Message, state: FSMContext, db: Database):
         chat_id=message.chat.id,
         state=state,
         render=make_chat_render_fn(db, state),
-        db=db,
-        bot_kind="client",
     )
     await controller.refresh_after_user_message(message)
diff --git a/app/handlers_client/start.py b/app/handlers_client/start.py
index dace81d..7a91691 100644
--- a/app/handlers_client/start.py
+++ b/app/handlers_client/start.py
@@ -14,7 +14,7 @@ router = Router()

 @router.message(CommandStart())
 async def start_cmd(message: Message, state: FSMContext, db: Database):
-    await clear_state_keep_screen(state, db, "client", message.chat.id)
+    await clear_state_keep_screen(state)
     await remember_client_screen(state, "main", {})
     await state.update_data(user_id=message.from_user.id)

@@ -23,9 +23,6 @@ async def start_cmd(message: Message, state: FSMContext, db: Database):
         chat_id=message.chat.id,
         state=state,
         render=lambda: render_client_screen(db, state),
-        db=db,
-        bot_kind="client",
     )
     await controller.delete_user_message(message)
-    await controller.delete_screen()
     await controller.refresh()
diff --git a/app/i18n/client/ru.py b/app/i18n/client/ru.py
new file mode 100644
index 0000000..80da379
--- /dev/null
+++ b/app/i18n/client/ru.py
@@ -0,0 +1,54 @@
+# Все тексты клиентского бота (RU)
+# Важно: ключи должны использоваться в клавиатурах и экранах вместо "жёстких" строк.
+
+TEXTS: dict[str, str] = {
+    # Главное меню (kb_client_main)
+    "main.order": "🛍 Заказать",
+    "main.orders": "📦 Заказы",
+    "main.chat": "💬 Чат",
+    "main.cabinet": "👤 Кабинет",
+
+    # Меню "Заказать" (kb_order_menu)
+    "order_menu.shops": "🛒 Магазины",
+    "order_menu.restaurants": "🍽 Рестораны",
+    "order_menu.cart": "🧺 Корзина",
+    "order_menu.history": "🕓 История",
+    "nav.home": "🏠 Главная",
+
+    # Навигация
+    "nav.back": "🔙 Назад",
+    "nav.home_alt": "🏠 Домой",
+    "nav.to_main": "🏠 В главное меню",
+
+    # Поиск
+    "search.open_inline": "🔎 Открыть inline",
+    "search.search": "🔎 Поиск",
+    "search.at_search": "🔎 @Поиск",
+
+    # Карточка товара
+    "product.add_to_cart": "➕ Добавить в корзину",
+
+    # Корзина
+    "cart.checkout": "🧾 Оформить заказ",
+    "cart.qty_suffix": "шт",  # используется в шаблоне количества: "{qty} {suffix}"
+    "cart.del_item_tpl": "❌ Удалить {name}",
+
+    # Оформление заказа
+    "checkout.choose_shop_tpl": "Оформить для точки ID {shop_id}",
+    "checkout.confirm": "✅ Подтвердить",
+
+    # Корзина по типам (kb_cart_menu)
+    "cart_menu.shop": "🛒 Корзина магазинов",
+    "cart_menu.restaurant": "🍽 Корзина ресторанов",
+
+    # Списки заказов/чатов
+    "orders.item_tpl": "Заказ #{order_id}",
+
+    # Карточка заказа (orders.py)
+    "order_card.chat": "💬 Чат по заказу",
+
+    # Кабинет (cabinet.py)
+    "cabinet.edit_name": "✏️ ФИО",
+    "cabinet.edit_phone": "📞 Телефон",
+    "cabinet.edit_address": "📍 Адрес",
+}
diff --git a/app/i18n/client/tj.py b/app/i18n/client/tj.py
new file mode 100644
index 0000000..9cb6e05
--- /dev/null
+++ b/app/i18n/client/tj.py
@@ -0,0 +1,54 @@
+# Ҳамаи матнҳои бот (Тоҷикӣ) — танҳо барои client
+# Эзоҳ: агар калид нест, бояд ба RU fallback шавад (дар translator.py).
+
+TEXTS: dict[str, str] = {
+    # Менюи асосӣ
+    "main.order": "🛍 Фармоиш",
+    "main.orders": "📦 Фармоишҳо",
+    "main.chat": "💬 Чат",
+    "main.cabinet": "👤 Кабинет",
+
+    # Менюи "Фармоиш"
+    "order_menu.shops": "🛒 Мағозаҳо",
+    "order_menu.restaurants": "🍽 Тарабхонаҳо",
+    "order_menu.cart": "🧺 Сабад",
+    "order_menu.history": "🕓 Таърих",
+    "nav.home": "🏠 Асосӣ",
+
+    # Навигатсия
+    "nav.back": "🔙 Бозгашт",
+    "nav.home_alt": "🏠 Асосӣ",
+    "nav.to_main": "🏠 Ба менюи асосӣ",
+
+    # Ҷустуҷӯ
+    "search.open_inline": "🔎 Inline-ро кушодан",
+    "search.search": "🔎 Ҷустуҷӯ",
+    "search.at_search": "🔎 @Ҷустуҷӯ",
+
+    # Корти маҳсулот
+    "product.add_to_cart": "➕ Ба сабад илова кардан",
+
+    # Сабад
+    "cart.checkout": "🧾 Фармоиш додан",
+    "cart.qty_suffix": "дона",
+    "cart.del_item_tpl": "❌ Нест кардан: {name}",
+
+    # Оформкунии фармоиш
+    "checkout.choose_shop_tpl": "Барои нуқтаи ID {shop_id} фармоиш додан",
+    "checkout.confirm": "✅ Тасдиқ",
+
+    # Сабадҳо аз рӯи намуд
+    "cart_menu.shop": "🛒 Сабади мағозаҳо",
+    "cart_menu.restaurant": "🍽 Сабади тарабхонаҳо",
+
+    # Рӯйхати фармоишҳо/чатҳо
+    "orders.item_tpl": "Фармоиш №{order_id}",
+
+    # Карточкаи фармоиш
+    "order_card.chat": "💬 Чат оид ба фармоиш",
+
+    # Кабинет
+    "cabinet.edit_name": "✏️ Ному насаб",
+    "cabinet.edit_phone": "📞 Телефон",
+    "cabinet.edit_address": "📍 Суроға",
+}
diff --git a/app/i18n/client/uz.py b/app/i18n/client/uz.py
new file mode 100644
index 0000000..824c49a
--- /dev/null
+++ b/app/i18n/client/uz.py
@@ -0,0 +1,54 @@
+# Client bot учун барча матнлар (Ўзбек тили, кириллица)
+# Эслатма: агар калит топилмаса, RU fallback бўлиши керак (translator.py).
+
+TEXTS: dict[str, str] = {
+    # Асосий меню
+    "main.order": "🛍 Буюртма",
+    "main.orders": "📦 Буюртмалар",
+    "main.chat": "💬 Чат",
+    "main.cabinet": "👤 Кабинет",
+
+    # "Буюртма" менюси
+    "order_menu.shops": "🛒 Дўконлар",
+    "order_menu.restaurants": "🍽 Ресторанлар",
+    "order_menu.cart": "🧺 Сават",
+    "order_menu.history": "🕓 Тарих",
+    "nav.home": "🏠 Бош саҳифа",
+
+    # Навигация
+    "nav.back": "🔙 Орқага",
+    "nav.home_alt": "🏠 Бош саҳифа",
+    "nav.to_main": "🏠 Асосий меню",
+
+    # Қидирув
+    "search.open_inline": "🔎 Inline очиш",
+    "search.search": "🔎 Қидирув",
+    "search.at_search": "🔎 @Қидирув",
+
+    # Маҳсулот карточкаси
+    "product.add_to_cart": "➕ Саватга қўшиш",
+
+    # Сават
+    "cart.checkout": "🧾 Буюртма бериш",
+    "cart.qty_suffix": "дона",
+    "cart.del_item_tpl": "❌ Ўчириш: {name}",
+
+    # Буюртмани расмийлаштириш
+    "checkout.choose_shop_tpl": "ID {shop_id} нуқтага буюртма бериш",
+    "checkout.confirm": "✅ Тасдиқлаш",
+
+    # Сават тури бўйича
+    "cart_menu.shop": "🛒 Дўкон савати",
+    "cart_menu.restaurant": "🍽 Ресторан савати",
+
+    # Буюртмалар / чатлар рўйхати
+    "orders.item_tpl": "Буюртма №{order_id}",
+
+    # Буюртма карточкаси
+    "order_card.chat": "💬 Буюртма бўйича чат",
+
+    # Кабинет
+    "cabinet.edit_name": "✏️ Исм-фамилия",
+    "cabinet.edit_phone": "📞 Телефон",
+    "cabinet.edit_address": "📍 Манзил",
+}
diff --git a/app/repositories/ui_screen_repo.py b/app/repositories/ui_screen_repo.py
deleted file mode 100644
index 3ec7429..0000000
--- a/app/repositories/ui_screen_repo.py
+++ /dev/null
@@ -1,51 +0,0 @@
-from __future__ import annotations
-
-from typing import Optional
-
-from app.db.database import Database
-
-
-class UiScreenRepo:
-    def __init__(self, db: Database):
-        self.db = db
-
-    async def get(self, bot_kind: str, chat_id: int) -> Optional[int]:
-        async with self.db.conn() as conn:
-            cur = await conn.execute(
-                """
-                SELECT screen_message_id
-                FROM ui_screens
-                WHERE bot_kind=? AND chat_id=?
-                """,
-                (bot_kind, chat_id),
-            )
-            row = await cur.fetchone()
-            if row and row["screen_message_id"] is not None:
-                return int(row["screen_message_id"])
-            return None
-
-    async def set(self, bot_kind: str, chat_id: int, screen_message_id: int) -> None:
-        async with self.db.conn() as conn:
-            await conn.execute(
-                """
-                INSERT INTO ui_screens (bot_kind, chat_id, screen_message_id, updated_at)
-                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
-                ON CONFLICT(bot_kind, chat_id) DO UPDATE SET
-                    screen_message_id=excluded.screen_message_id,
-                    updated_at=CURRENT_TIMESTAMP
-                """,
-                (bot_kind, chat_id, screen_message_id),
-            )
-            await conn.commit()
-
-    async def clear(self, bot_kind: str, chat_id: int) -> None:
-        async with self.db.conn() as conn:
-            await conn.execute(
-                """
-                UPDATE ui_screens
-                SET screen_message_id=NULL, updated_at=CURRENT_TIMESTAMP
-                WHERE bot_kind=? AND chat_id=?
-                """,
-                (bot_kind, chat_id),
-            )
-            await conn.commit()
diff --git a/app/services/chat_screen_controller.py b/app/services/chat_screen_controller.py
index 8e01fed..e366967 100644
--- a/app/services/chat_screen_controller.py
+++ b/app/services/chat_screen_controller.py
@@ -1,16 +1,14 @@
 from __future__ import annotations
-import inspect
+^M
 from dataclasses import dataclass
 from typing import Awaitable, Callable, Optional, Tuple

 from aiogram.types import InlineKeyboardMarkup, Message
 from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

-from app.db.database import Database
-from app.repositories.ui_screen_repo import UiScreenRepo

 RenderResult = Tuple[str, Optional[InlineKeyboardMarkup]]
-RenderFn = Callable[[], RenderResult | Awaitable[RenderResult]]
+RenderFn = Callable[[], Awaitable[RenderResult]]^M


 @dataclass
@@ -27,33 +25,9 @@ class ChatScreenController:
     chat_id: int
     state: any  # FSMContext
     render: RenderFn
-    db: Database
-    bot_kind: str

     SCREEN_KEY: str = "screen_message_id"

-    @property
-    def _repo(self) -> UiScreenRepo:
-        return UiScreenRepo(self.db)
-
-    async def _get_screen_id(self) -> Optional[int]:
-        data = await self.state.get_data()
-        prev_id = data.get(self.SCREEN_KEY)
-        if prev_id:
-            return int(prev_id)
-        prev_id = await self._repo.get(self.bot_kind, self.chat_id)
-        if prev_id:
-            await self.state.update_data(**{self.SCREEN_KEY: prev_id})
-        return prev_id
-
-    async def _set_screen_id(self, message_id: int) -> None:
-        await self.state.update_data(**{self.SCREEN_KEY: message_id})
-        await self._repo.set(self.bot_kind, self.chat_id, message_id)
-
-    async def _clear_screen_id(self) -> None:
-        await self.state.update_data(**{self.SCREEN_KEY: None})
-        await self._repo.clear(self.bot_kind, self.chat_id)
-
     async def _safe_delete(self, message_id: int) -> None:
         try:
             await self.bot.delete_message(self.chat_id, message_id)
@@ -75,29 +49,24 @@ class ChatScreenController:

     async def delete_screen(self) -> None:
 #        """Удалить текущий экран (сообщение бота), если есть."""
-        prev_id = await self._get_screen_id()
+        data = await self.state.get_data()^M
+        prev_id = data.get(self.SCREEN_KEY)^M
         if prev_id:
             await self._safe_delete(int(prev_id))
-        await self._clear_screen_id()
+            await self.state.update_data(**{self.SCREEN_KEY: None})^M

     async def refresh(self) -> int:
-        prev_id = await self._get_screen_id()
+ #       """^M
+  #        """^M
+        data = await self.state.get_data()^M
+        prev_id = data.get(self.SCREEN_KEY)^M
         if prev_id:
             await self._safe_delete(int(prev_id))
-
-        result = self.render()
-        if inspect.isawaitable(result):
-            result = await result
-
-        text, markup = result
-
-        sent = await self.bot.send_message(
-            self.chat_id,
-            text,
-            reply_markup=markup,
-        )
-
-        await self._set_screen_id(sent.message_id)
+^M
+        text, markup = await self.render()^M
+        sent = await self.bot.send_message(self.chat_id, text, reply_markup=markup)^M
+^M
+        await self.state.update_data(**{self.SCREEN_KEY: sent.message_id})^M
         return sent.message_id

     async def refresh_after_user_message(self, message: Message) -> int:
diff --git a/app/services/screen.py b/app/services/screen.py
index 1256d6e..cd06a26 100644
--- a/app/services/screen.py
+++ b/app/services/screen.py
@@ -5,91 +5,66 @@ from aiogram.fsm.context import FSMContext
 from aiogram.types import InlineKeyboardMarkup
 from aiogram.exceptions import TelegramBadRequest

-from app.db.database import Database
-from app.repositories.ui_screen_repo import UiScreenRepo
-
 SCREEN_MESSAGE_ID_KEY = "screen_message_id"


-async def get_screen_message_id(
-    state: FSMContext,
-    db: Database,
-    bot_kind: str,
-    chat_id: int,
-) -> int | None:
+async def get_screen_message_id(state: FSMContext) -> int | None:
     data = await state.get_data()
-    screen_message_id = data.get(SCREEN_MESSAGE_ID_KEY)
-    if screen_message_id:
-        return int(screen_message_id)
-    repo = UiScreenRepo(db)
-    screen_message_id = await repo.get(bot_kind, chat_id)
-    if screen_message_id:
-        await state.update_data({SCREEN_MESSAGE_ID_KEY: screen_message_id})
-    return screen_message_id
+    return data.get(SCREEN_MESSAGE_ID_KEY)


-async def set_screen_message_id(
-    state: FSMContext,
-    db: Database,
-    bot_kind: str,
-    chat_id: int,
-    message_id: int,
-) -> None:
+async def set_screen_message_id(state: FSMContext, message_id: int) -> None:
     await state.update_data({SCREEN_MESSAGE_ID_KEY: message_id})
-    repo = UiScreenRepo(db)
-    await repo.set(bot_kind, chat_id, message_id)


-async def clear_screen_message_id(state: FSMContext, db: Database, bot_kind: str, chat_id: int) -> None:
+async def clear_screen_message_id(state: FSMContext) -> None:
     await state.update_data({SCREEN_MESSAGE_ID_KEY: None})
-    repo = UiScreenRepo(db)
-    await repo.clear(bot_kind, chat_id)


-async def clear_state_keep_screen(state: FSMContext, db: Database, bot_kind: str, chat_id: int) -> None:
-    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
+async def clear_state_keep_screen(state: FSMContext) -> None:
+    screen_message_id = await get_screen_message_id(state)
     await state.clear()
     if screen_message_id:
-        await set_screen_message_id(state, db, bot_kind, chat_id, screen_message_id)
+        await set_screen_message_id(state, screen_message_id)


-async def delete_screen(
-    bot: Bot,
-    chat_id: int,
-    state: FSMContext,
-    db: Database,
-    bot_kind: str,
-) -> None:
-    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
-    if screen_message_id:
-        try:
-            await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
-        except Exception:
-            # Безопасно игнорируем, чтобы не зациклиться на недоступном сообщении.
-            pass
-    await clear_screen_message_id(state, db, bot_kind, chat_id)
+async def delete_screen(bot: Bot, chat_id: int, state: FSMContext) -> None:
+    screen_message_id = await get_screen_message_id(state)
+    if not screen_message_id:
+        return
+    try:
+        await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
+    except Exception:
+        # Безопасно игнорируем, чтобы не зациклиться на недоступном сообщении.
+        pass
+    await clear_screen_message_id(state)


 async def show_screen(
     bot: Bot,
     chat_id: int,
     state: FSMContext,
-    db: Database,
-    bot_kind: str,
     text: str,
     reply_markup: InlineKeyboardMarkup | None,
 ) -> int:
-    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
+    screen_message_id = await get_screen_message_id(state)
     if screen_message_id:
         try:
-            await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
-        except TelegramBadRequest:
-            pass
+            await bot.edit_message_text(
+                text=text,
+                chat_id=chat_id,
+                message_id=screen_message_id,
+                reply_markup=reply_markup,
+            )
+            return screen_message_id
+        except TelegramBadRequest as exc:
+            if "message is not modified" in str(exc):
+                return screen_message_id
         except Exception:
             pass

     message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
-    await set_screen_message_id(state, db, bot_kind, chat_id, message.message_id)
+    await set_screen_message_id(state, message.message_id)
     return message.message_id


@@ -97,8 +72,6 @@ async def show_main_menu(
     bot: Bot,
     chat_id: int,
     state: FSMContext,
-    db: Database,
-    bot_kind: str,
     text: str,
     reply_markup: InlineKeyboardMarkup,
 ) -> int:
@@ -106,8 +79,6 @@ async def show_main_menu(
         bot=bot,
         chat_id=chat_id,
         state=state,
-        db=db,
-        bot_kind=bot_kind,
         text=text,
         reply_markup=reply_markup,
     )
diff --git a/app/utils/tg_safe.py b/app/utils/tg_safe.py
deleted file mode 100644
index 2ab2ed6..0000000
--- a/app/utils/tg_safe.py
+++ /dev/null
@@ -1,22 +0,0 @@
-from __future__ import annotations
-
-from aiogram.exceptions import TelegramBadRequest
-from aiogram.types import InlineKeyboardMarkup, Message
-
-
-async def safe_edit_text(
-    msg: Message,
-    text: str,
-    reply_markup: InlineKeyboardMarkup | None = None,
-) -> bool:
-   # """
-    #Áåçîïàñíî ðåäàêòèðóåò ñîîáùåíèå.
-    #Âîçâðàùàåò True åñëè îòðåäàêòèðîâàëè, False åñëè Telegram îòâåòèë 'message is not modified'.
-    #"""
-    try:
-        await msg.edit_text(text, reply_markup=reply_markup)
-        return True
-    except TelegramBadRequest as e:
-        if "message is not modified" in str(e):
-            return False
-        raise
