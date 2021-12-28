CREATE TABLE IF NOT EXISTS command_config
(
    server_id bigint NOT NULL,
    entity_id bigint,
    command text COLLATE pg_catalog."default" NOT NULL
)
