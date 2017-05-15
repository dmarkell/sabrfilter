DROP TABLE IF EXISTS sabrfilter_batting;
CREATE TABLE IF NOT EXISTS sabrfilter_batting (
    team character varying(3),
    year INT,
    full_name text,
    playerid character varying(10),
    stint int,
    ab int,
    h int,
    bb int,
    hbp int,
    sb int,
    cs int,
    hr int,
    r int,
    rbi int,
    pa int,
    lgid character varying(2),
    pos text,
    pos_arr json
);