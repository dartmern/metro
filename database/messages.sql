CREATE TABLE IF NOT EXISTS messages
(
    index bigint NOT NULL,
    unix real,
    "timestamp" timestamp without time zone,
    message_id bigint,
    author_id bigint,
    channel_id bigint,
    server_id bigint,
    deleted boolean DEFAULT false,
    edited boolean DEFAULT false,
    CONSTRAINT messages_pkey PRIMARY KEY (index)
)

