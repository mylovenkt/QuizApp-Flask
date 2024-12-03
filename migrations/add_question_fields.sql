-- First create a backup of the question table
CREATE TABLE IF NOT EXISTS question_backup AS SELECT * FROM question;

-- Drop the existing table
DROP TABLE IF EXISTS question;

-- Recreate the question table with all columns
CREATE TABLE IF NOT EXISTS question (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL DEFAULT 'multiple_choice',
    image_url VARCHAR(200),
    option1 VARCHAR,
    option2 VARCHAR,
    option3 VARCHAR,
    option4 VARCHAR,
    correct_option CHAR NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT 0,
    creator_id INTEGER NOT NULL,
    question_set_id INTEGER,
    category_id INTEGER,
    difficulty VARCHAR(20) DEFAULT 'medium',
    content TEXT,
    explanation TEXT,
    tags JSON,
    media_urls JSON,
    difficulty_level INTEGER DEFAULT 1,
    last_modified DATETIME DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (creator_id) REFERENCES user (id),
    FOREIGN KEY (question_set_id) REFERENCES questionset (id),
    FOREIGN KEY (category_id) REFERENCES category (id)
);

-- Copy data back from backup
INSERT INTO question (
    id, question, question_type, image_url, option1, option2, option3, option4,
    correct_option, verified, creator_id, question_set_id, category_id, difficulty,
    content, explanation, tags, media_urls, difficulty_level, version
)
SELECT 
    id, question, question_type, image_url, option1, option2, option3, option4,
    correct_option, verified, creator_id, question_set_id, category_id, difficulty,
    content, explanation, tags, media_urls, difficulty_level, version
FROM question_backup;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_question_difficulty_level ON question(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_question_last_modified ON question(last_modified);
CREATE INDEX IF NOT EXISTS idx_question_creator ON question(creator_id);
CREATE INDEX IF NOT EXISTS idx_question_category ON question(category_id);

-- Drop the backup table
DROP TABLE question_backup;