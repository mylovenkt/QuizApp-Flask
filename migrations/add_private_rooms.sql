-- Add new columns to chat_room table
ALTER TABLE chat_room ADD COLUMN is_private BOOLEAN DEFAULT FALSE;
ALTER TABLE chat_room ADD COLUMN passcode VARCHAR(6);
ALTER TABLE chat_room ADD COLUMN creator_id INTEGER REFERENCES user(id); 