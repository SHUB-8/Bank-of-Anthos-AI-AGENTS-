FROM postgres:13-alpine

# Set working directory
WORKDIR /docker-entrypoint-initdb.d

# Copy schema file from local context
COPY 0001_create_ai_meta_tables.sql ./

# Expose default PostgreSQL port
EXPOSE 5432
