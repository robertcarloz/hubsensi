-- HubSensi Database Initialization Script
-- This script runs when PostgreSQL container starts

-- Create additional extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone
SET TIMEZONE = 'Asia/Jakarta';

-- Create additional users or roles if needed
-- Note: The main user and database are created by Docker environment variables

-- Create schema for better organization (optional)
CREATE SCHEMA IF NOT EXISTS hubsensi AUTHORIZATION hubsensi_user;

-- Set default permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hubsensi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hubsensi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO hubsensi_user;