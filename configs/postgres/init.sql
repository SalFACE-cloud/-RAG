-- PostgreSQL 初始化脚本（Phase 1 基础设施）
-- 数据库 edu_kb 由 POSTGRES_DB 环境变量创建

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 用户（小程序 / JWT 关联，Phase 6+ 使用）
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(128) UNIQUE NOT NULL,
    nickname VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 音频资源元数据（生产环境替代 data/audio_seed.json）
CREATE TABLE IF NOT EXISTS audio_assets (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    subject VARCHAR(16),
    oss_url TEXT,
    duration_sec INTEGER,
    transcript_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 测评提交记录
CREATE TABLE IF NOT EXISTS assessment_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    knowledge_id VARCHAR(32),
    answers JSONB NOT NULL DEFAULT '[]',
    score NUMERIC(5, 2),
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- 音频训练提交
CREATE TABLE IF NOT EXISTS audio_training_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    audio_id VARCHAR(64) NOT NULL,
    answers JSONB NOT NULL DEFAULT '[]',
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessment_user ON assessment_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_audio_training_user ON audio_training_submissions(user_id);
