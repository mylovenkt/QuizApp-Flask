-- Create message reactions table
CREATE TABLE message_reaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reaction VARCHAR(10) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES message (id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    UNIQUE (message_id, user_id, reaction)
);

-- Create indexes
CREATE INDEX idx_reaction_message ON message_reaction(message_id);
CREATE INDEX idx_reaction_user ON message_reaction(user_id); 