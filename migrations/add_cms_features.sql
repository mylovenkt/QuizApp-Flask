-- Add new columns to question table
ALTER TABLE question ADD COLUMN content TEXT;
ALTER TABLE question ADD COLUMN explanation TEXT;
ALTER TABLE question ADD COLUMN tags JSON;
ALTER TABLE question ADD COLUMN media_urls JSON;
ALTER TABLE question ADD COLUMN difficulty_level INTEGER DEFAULT 1;
ALTER TABLE question ADD COLUMN last_modified DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE question ADD COLUMN version INTEGER DEFAULT 1;

-- Create index for better search performance
CREATE INDEX idx_question_tags ON question((json_extract(tags, '$[*]')));
CREATE INDEX idx_question_difficulty ON question(difficulty_level);
CREATE INDEX idx_question_modified ON question(last_modified);