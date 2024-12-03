-- Create chat_room table if not exists
CREATE TABLE IF NOT EXISTS chat_room (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    quiz_set_id INTEGER,
    question_id INTEGER,
    is_private BOOLEAN DEFAULT FALSE,
    passcode VARCHAR(6),
    creator_id INTEGER,
    FOREIGN KEY (quiz_set_id) REFERENCES questionset(id),
    FOREIGN KEY (question_id) REFERENCES question(id),
    FOREIGN KEY (creator_id) REFERENCES user(id)
);

-- Create message table if not exists
CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (room_id) REFERENCES chat_room(id)
);

-- Create chat_participants table if not exists
CREATE TABLE IF NOT EXISTS chat_participants (
    user_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, room_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (room_id) REFERENCES chat_room(id)
);

-- Create indexes
CREATE INDEX idx_message_room ON message(room_id);
CREATE INDEX idx_message_user ON message(user_id);
CREATE INDEX idx_chatroom_type ON chat_room(type); 