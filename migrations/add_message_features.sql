-- Add new columns to message table
ALTER TABLE message ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE message ADD COLUMN deleted_at DATETIME; 