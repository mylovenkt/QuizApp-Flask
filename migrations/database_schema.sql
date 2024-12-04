-- Question Table Modifications
ALTER TABLE question ADD COLUMN content TEXT;
ALTER TABLE question ADD COLUMN explanation TEXT;
ALTER TABLE question ADD COLUMN tags JSON;
ALTER TABLE question ADD COLUMN media_urls JSON;
ALTER TABLE question ADD COLUMN difficulty_level INTEGER DEFAULT 1;
ALTER TABLE question ADD COLUMN last_modified DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE question ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE question ADD COLUMN created_at DATETIME;

-- User Table Modifications
ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0;

-- Question Indexes
CREATE INDEX IF NOT EXISTS idx_question_tags ON question((json_extract(tags, '$[*]')));
CREATE INDEX IF NOT EXISTS idx_question_difficulty ON question(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_question_modified ON question(last_modified);
CREATE INDEX IF NOT EXISTS idx_question_creator ON question(creator_id);
CREATE INDEX IF NOT EXISTS idx_question_category ON question(category_id);

-- Chat System Tables
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

CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_by INTEGER,
    deleted_at DATETIME,
    is_read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (room_id) REFERENCES chat_room(id),
    FOREIGN KEY (deleted_by) REFERENCES user(id)
);

-- Message Reactions
CREATE TABLE IF NOT EXISTS message_reaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reaction VARCHAR(10) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES message (id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    UNIQUE (message_id, user_id, reaction)
);

-- Message Reports
CREATE TABLE IF NOT EXISTS message_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (message_id) REFERENCES message (id),
    FOREIGN KEY (reporter_id) REFERENCES user (id)
);

CREATE TABLE IF NOT EXISTS chat_participants (
    user_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, room_id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (room_id) REFERENCES chat_room(id)
);

-- Chat System Indexes
CREATE INDEX IF NOT EXISTS idx_message_room ON message(room_id);
CREATE INDEX IF NOT EXISTS idx_message_user ON message(user_id);
CREATE INDEX IF NOT EXISTS idx_chatroom_type ON chat_room(type);
CREATE INDEX IF NOT EXISTS idx_message_deleted ON message(is_deleted);
CREATE INDEX IF NOT EXISTS idx_report_status ON message_report(status);
CREATE INDEX IF NOT EXISTS idx_reaction_message ON message_reaction(message_id);
CREATE INDEX IF NOT EXISTS idx_reaction_user ON message_reaction(user_id);

-- Notification System
CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(20) DEFAULT 'info',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT 0,
    action_taken BOOLEAN DEFAULT 0,
    priority VARCHAR(10) DEFAULT 'normal',
    expiry_date DATETIME,
    extra_data JSON,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- Notification Indexes
CREATE INDEX IF NOT EXISTS idx_notification_user ON notification(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_read ON notification(is_read);

-- Quiz Sets
CREATE TABLE IF NOT EXISTS user_quiz_sets (
    user_id INTEGER NOT NULL,
    quiz_set_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, quiz_set_id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (quiz_set_id) REFERENCES questionset (id)
);

-- Quiz Sets Indexes
CREATE INDEX IF NOT EXISTS idx_user_quiz_sets ON user_quiz_sets(user_id, quiz_set_id); 