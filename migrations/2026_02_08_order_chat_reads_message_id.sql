ALTER TABLE order_chat_reads
ADD COLUMN last_read_message_id INTEGER NOT NULL DEFAULT 0;
