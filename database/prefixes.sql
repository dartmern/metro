CREATE TABLE IF NOT EXISTS prefixes
(
    prefix text COLLATE pg_catalog."default" NOT NULL,
    guild_id bigint NOT NULL,
    CONSTRAINT guild_id UNIQUE (guild_id, prefix),
    CONSTRAINT prefix UNIQUE (prefix, guild_id)
)