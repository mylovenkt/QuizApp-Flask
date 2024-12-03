-- Add read receipts table
CREATE TABLE message_read (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES message (id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    UNIQUE (message_id, user_id)
);

-- Create indexes
CREATE INDEX idx_read_message ON message_read(message_id);
CREATE INDEX idx_read_user ON message_read(user_id); 