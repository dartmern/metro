CREATE TABLE IF NOT EXISTS notes
(
    note_id BIGSERIAL PRIMARY KEY,
    user_id bigint NOT NULL,
    text text NOT NULL,
    added_time timestamp without time zone NOT NULL

)