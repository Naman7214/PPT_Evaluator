import sqlite3
from flask import g, current_app

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(current_app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with current_app.app_context():
        db = get_db()
        with current_app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def close_db(e=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    result = cur.fetchall()
    cur.close()
    column_names = [column[0] for column in cur.description]

    if not result:
        return None

    if one:
        return dict(zip(column_names, result[0]))

    return [dict(zip(column_names, row)) for row in result]

def insert_db(query, args=()):
    db = get_db()
    db.execute(query, args)
    db.commit()

def update_db(query, args=()):
    db = get_db()
    db.execute(query, args)
    db.commit()

