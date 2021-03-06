"""
Python object to work with PostgreSQL object inventory

Author: Pete Ezzo <peter.ezzo@gmail.com>
"""

import psycopg2  # type: ignore


class InventoryDB():
    def __init__(self, host, dbname, user, password, sslmode='prefer'):
        conn_string = f'host={host} user={user} dbname={dbname} password={password} sslmode={sslmode}'
        self.connection = psycopg2.connect(conn_string)
        self.connection.autocommit = True
        # self.connection.set_trace_callback(print)  # activate query debugging
        self.cursor = self.connection.cursor()

        self.initdb()

    def initdb(self):
        schema = '''create table if not exists Inventory (
                    id serial primary key,
                    src text,
                    meta text,
                    name text,
                    created timestamp NOT NULL DEFAULT NOW(),
                    lastseen timestamp NOT NULL DEFAULT NOW(),
                    unique (src, meta, name));'''
        self.cursor.execute(schema)

    def add_record(self, src, meta, name):
        query = 'insert into Inventory (src, meta, name) values (%s, %s, %s) ' + \
                'on conflict (src, meta, name) do update set lastseen = NOW();'
        self.cursor.execute(query, (src, meta, name))

    def search_all(self, searchstr):
        query = "select * from Inventory where name ~* %s " + \
                "and lastseen > NOW() - interval '2 days' order by name;"
        return self._search(query, (searchstr,))

    def search_names(self, searchstr):
        query = "select distinct name, meta from Inventory where name ~* %s " + \
                "and lastseen > NOW() - interval '2 days' order by name;"
        return self._search(query, (searchstr,))

    def search_all_by_src(self, searchstr):
        query = "select * from Inventory where src ~* %s " + \
                "and lastseen > NOW() - interval '2 days' order by name;"
        return self._search(query, (searchstr,))

    def _search(self, query: str, params: tuple):
        self.cursor.execute(query, (params))
        return self.cursor.fetchall()
