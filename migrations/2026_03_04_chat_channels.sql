ALTER TABLE order_chat_messages
ADD COLUMN channel TEXT;

UPDATE order_chat_messages
SET channel = CASE
    WHEN thread = 'merchant' THEN 'client_merchant'
    WHEN thread = 'courier_client' THEN 'client_courier'
    WHEN thread = 'courier' THEN 'merchant_courier'
    WHEN thread IS NULL THEN 'client_merchant'
    ELSE 'client_merchant'
END
WHERE channel IS NULL OR TRIM(channel) = '';

CREATE TABLE IF NOT EXISTS order_chat_reads_new (
    order_id INTEGER NOT NULL,
    viewer_role TEXT NOT NULL,
    viewer_user_id INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'client_merchant',
    last_read_at DATETIME NOT NULL,
    PRIMARY KEY (order_id, viewer_role, viewer_user_id, channel),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

INSERT OR REPLACE INTO order_chat_reads_new(order_id, viewer_role, viewer_user_id, channel, last_read_at)
SELECT order_id, viewer_role, viewer_user_id, 'client_merchant', last_read_at
FROM order_chat_reads;

DROP TABLE order_chat_reads;
ALTER TABLE order_chat_reads_new RENAME TO order_chat_reads;

CREATE INDEX IF NOT EXISTS idx_chat_order_channel ON order_chat_messages(order_id, channel, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_reads_viewer ON order_chat_reads(viewer_role, viewer_user_id);
