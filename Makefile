.PHONY: run seed-admin-jobs

POSTGRES_HOST ?= localhost
POSTGRES_PORT ?= 5432
POSTGRES_DB ?= redaction
POSTGRES_USER ?= redaction
POSTGRES_PASSWORD ?= redaction

run:
	docker-compose down -v --remove-orphans
	docker-compose up --build

seed-admin-jobs:
	PGPASSWORD=$(POSTGRES_PASSWORD) psql -h $(POSTGRES_HOST) -p $(POSTGRES_PORT) -U $(POSTGRES_USER) -d $(POSTGRES_DB) -c "WITH admin_user AS (SELECT id FROM users WHERE username = 'admin') INSERT INTO jobs (id, user_id, name, filename, status, source_object_key, result_object_key, content_type, result_content_type, error_message, created_at) SELECT gen_random_uuid()::text, admin_user.id, format('Seed Job %s', seq.n), format('seed-image-%s.jpg', seq.n), 'queued', NULL, NULL, 'image/jpeg', NULL, NULL, NOW() - make_interval(mins => seq.n) FROM admin_user CROSS JOIN generate_series(1, 50) AS seq(n);"
