import datetime
import json
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash, send_from_directory
from flask.ext.heroku import Heroku
from contextlib import closing
import os

TOKEN = os.environ['TOKEN']
app = Flask(__name__)

is_prod = os.environ.get('IS_HEROKU', None)
if is_prod:
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    heroku = Heroku(app)

else:
    app.config['DEBUG'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = "{}/{}".format(
        os.environ['PG_DATABASE_PATH'],
        os.environ['PG_DATABASE_NAME']
    )

db_con = psycopg2.connect()

@app.route('/')
def render_page():
    return app.send_static_file('index.html')

@app.route('/data')
def query_db():

    cursor = db_con.cursor(cursor_factory=RealDictCursor)
    query = 'SELECT * FROM sabrfilter'
    cursor.execute(query)
    output = [dict(row) for row in cursor]
    payload = json.dumps(output)

    return payload

if __name__ == "__main__":
    app.run()
