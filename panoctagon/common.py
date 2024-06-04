import sqlite3
from dataclasses import dataclass, astuple, fields


def write_tuples_to_db(con: sqlite3.Connection, tbl_name: str, data: list[dataclass]):
    cur = con.cursor()
    col_names = [f.name for f in fields(data[0])]
    n_cols = len(col_names)
    headers = ",".join(col_names)
    tuples = [astuple(i) for i in data]
    placeholders = ", ".join(["?"] * n_cols)

    query = f"INSERT INTO {tbl_name} ({headers}) VALUES ({placeholders})"
    cur.executemany(query, tuples)
    con.commit()
