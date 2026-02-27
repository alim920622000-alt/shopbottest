ALTER TABLE order_chat_messages
ADD COLUMN thread TEXT NOT NULL DEFAULT 'merchant';

CREATE TABLE IF NOT EXISTS chat_prefs (
    order_id INTEGER NOT NULL,
    actor_role TEXT NOT NULL,
    actor_id INTEGER NOT NULL,
    thread TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (order_id, actor_role, actor_id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
