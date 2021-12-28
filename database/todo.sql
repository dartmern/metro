CREATE TABLE IF NOT EXISTS todo
(
    user_id bigint NOT NULL,
    text text COLLATE pg_catalog."default" NOT NULL,
    jump_url text COLLATE pg_catalog."default" NOT NULL,
    added_time time without time zone NOT NULL,
    CONSTRAINT text UNIQUE (text, user_id),
    CONSTRAINT user_id UNIQUE (user_id, text)
)