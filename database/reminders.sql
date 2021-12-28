CREATE TABLE IF NOT EXISTS reminders
(
    id bigint NOT NULL,
    event text COLLATE pg_catalog."default" NOT NULL,
    extra jsonb NOT NULL,
    expires timestamp without time zone NOT NULL,
    created timestamp without time zone NOT NULL,
    CONSTRAINT reminders_pkey PRIMARY KEY (id)
)
