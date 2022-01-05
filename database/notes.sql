CREATE TABLE IF NOT EXISTS notes
(
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    text text NOT NULL,
    added_time timestamp without time zone NOT NULL,
    author_id bigint NOT NULL

)