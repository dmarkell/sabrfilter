
import datetime
import json
import psycopg2
import requests

from psycopg2.extras import RealDictCursor
from flask import Flask, request, session, g, redirect, url_for, abort, \
    render_template, flash, send_from_directory
from flask.ext.heroku import Heroku
from contextlib import closing
import urlparse
import os

TOKEN = os.environ['TOKEN']
app = Flask(__name__)

is_prod = os.environ.get('IS_HEROKU', None)
if is_prod:
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    heroku = Heroku(app)
    db_con = psycopg2.connect()

else:
    app.config['DEBUG'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = "{}/{}".format(
        os.environ['PG_DATABASE_PATH'],
        os.environ['PG_DATABASE_NAME']
    )
    urlparse.uses_netloc.append("postgres")
    url = urlparse.urlparse(os.environ["DATABASE_URL"])

    db_con = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )



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
