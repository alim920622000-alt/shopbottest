CREATE TABLE IF NOT EXISTS notif_center_state (
    bot_kind TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (bot_kind, chat_id)
);
