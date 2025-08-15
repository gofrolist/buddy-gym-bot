-- Table: users
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    tg_user_id BIGINT UNIQUE NOT NULL,
    handle VARCHAR(64),
    tz VARCHAR(32) DEFAULT 'UTC',
    units VARCHAR(8) DEFAULT 'kg',
    last_lang VARCHAR(8) DEFAULT 'en',
    premium_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for tg_user_id
CREATE INDEX IF NOT EXISTS idx_users_tg_user_id ON users (tg_user_id);

-- Table: referrals
CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    inviter_user_id INTEGER REFERENCES users(id),
    invitee_user_id INTEGER REFERENCES users(id),
    token VARCHAR(64) UNIQUE NOT NULL,
    reward_days INTEGER DEFAULT 30,
    status VARCHAR(16) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fulfilled_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for referrals table
CREATE INDEX IF NOT EXISTS idx_referrals_inviter_user_id ON referrals (inviter_user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_invitee_user_id ON referrals (invitee_user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_token ON referrals (token);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals (status);

-- Table: workout_sessions
CREATE TABLE IF NOT EXISTS workout_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    title VARCHAR(120)
);

-- Index for user_id in workout_sessions
CREATE INDEX IF NOT EXISTS idx_workout_sessions_user_id ON workout_sessions (user_id);

-- Table: set_rows
CREATE TABLE IF NOT EXISTS set_rows (
    id BIGSERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES workout_sessions(id),
    exercise VARCHAR(120) NOT NULL,
    weight_kg FLOAT NOT NULL,
    reps INTEGER NOT NULL,
    rpe FLOAT,
    is_warmup BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for session_id in set_rows
CREATE INDEX IF NOT EXISTS idx_set_rows_session_id ON set_rows (session_id);
