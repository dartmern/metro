CREATE TABLE IF NOT EXISTS blacklist
(
    member_id bigint NOT NULL,
    is_blacklisted boolean NOT NULL,
    moderator bigint NOT NULL,
    added_time timestamp without time zone NOT NULL,
    reason text COLLATE pg_catalog."default",
    CONSTRAINT is_blacklisted UNIQUE (is_blacklisted, member_id),
    CONSTRAINT member_id UNIQUE (member_id, is_blacklisted)
)
