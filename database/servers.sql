CREATE TABLE IF NOT EXISTS servers
(
    server_id bigint NOT NULL,
    muterole bigint,
    CONSTRAINT servers_pkey PRIMARY KEY (server_id)
)