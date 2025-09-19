#!/bin/bash

# HubSensi Database Initialization Script
# This script sets up the PostgreSQL database for HubSensi application

set -e  # Exit on error

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found. Please create it from .env.example"
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}HubSensi Database Initialization Script${NC}"
echo "============================================="

# Check if PostgreSQL is running
if ! pg_isready -h $DB_HOST -p $DB_PORT > /dev/null 2>&1; then
    echo -e "${RED}PostgreSQL is not running on $DB_HOST:$DB_PORT${NC}"
    echo "Please start PostgreSQL and try again"
    exit 1
fi

# Create database and user
echo -e "${YELLOW}Creating database and user...${NC}"

# Create the database user
psql -h $DB_HOST -p $DB_PORT -U $PG_SUPERUSER -c "
    CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
" postgres

# Create the database
psql -h $DB_HOST -p $DB_PORT -U $PG_SUPERUSER -c "
    CREATE DATABASE $DB_NAME 
    WITH OWNER = $DB_USER 
    ENCODING = 'UTF8' 
    LC_COLLATE = 'en_US.UTF-8' 
    LC_CTYPE = 'en_US.UTF-8' 
    TEMPLATE = template0;
" postgres

# Grant privileges
psql -h $DB_HOST -p $DB_PORT -U $PG_SUPERUSER -c "
    GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
    ALTER USER $DB_USER CREATEDB;
" postgres

echo -e "${GREEN}Database and user created successfully!${NC}"

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
flask db upgrade

echo -e "${GREEN}Database initialization completed successfully!${NC}"
echo "============================================="
echo "Database Name: $DB_NAME"
echo "Database User: $DB_USER"
echo "Database Host: $DB_HOST"
echo "Database Port: $DB_PORT"
echo "============================================="