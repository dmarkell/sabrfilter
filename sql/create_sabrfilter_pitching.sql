DROP TABLE IF EXISTS sabrfilter_pitching;
CREATE TABLE IF NOT EXISTS sabrfilter_pitching (
    team character varying(3),
    year INT,
    full_name text,
    playerid character varying(10),
    stint int,
    w int,
    l int,
    sv int,
    ip double precision,
    g int,
    gs int,
    so int,
    bb int,
    h int,
    er int,
    lgid character varying(2),
    pos text,
    pos_arr json
);