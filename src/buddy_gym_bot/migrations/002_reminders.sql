-- Table: reminders
CREATE TABLE IF NOT EXISTS reminders (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    job_id VARCHAR(64) UNIQUE NOT NULL,
    run_at TIMESTAMP WITH TIME ZONE NOT NULL,
    message VARCHAR(255) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reminders_chat_id ON reminders (chat_id);
CREATE INDEX IF NOT EXISTS idx_reminders_run_at ON reminders (run_at);
