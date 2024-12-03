-- Add moderation fields to message table
ALTER TABLE message ADD COLUMN is_deleted BOOLEAN DEFAULT 0;
ALTER TABLE message ADD COLUMN deleted_by INTEGER REFERENCES user(id);
ALTER TABLE message ADD COLUMN deleted_at DATETIME;

-- Create message reports table
CREATE TABLE message_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (message_id) REFERENCES message (id),
    FOREIGN KEY (reporter_id) REFERENCES user (id)
);

-- Create indexes
CREATE INDEX idx_message_deleted ON message(is_deleted);
CREATE INDEX idx_report_status ON message_report(status); 