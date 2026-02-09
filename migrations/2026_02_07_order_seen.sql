CREATE TABLE IF NOT EXISTS order_seen (
    order_id INTEGER NOT NULL,
    viewer_role TEXT NOT NULL,
    viewer_user_id INTEGER NOT NULL,
    seen_at DATETIME NOT NULL,
    PRIMARY KEY (order_id, viewer_role, viewer_user_id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_order_seen_viewer ON order_seen(viewer_role, viewer_user_id);
