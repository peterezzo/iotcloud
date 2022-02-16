create table if not exists Inventory (
    id serial primary key,
    src text,
    meta text,
    name text,
    created timestamp NOT NULL DEFAULT NOW(),
    lastseen timestamp NOT NULL DEFAULT NOW(),
    unique (src, meta, name)
);
