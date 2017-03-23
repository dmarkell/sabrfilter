
from bs4 import BeautifulSoup
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
    urlparse.uses_netloc.append("postgres")
    url = urlparse.urlparse(os.environ["DATABASE_URL"])

    db_con = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

else:
    app.config['DEBUG'] = True
    db_con = psycopg2.connect(host='')

def send_pitcher_webhook(payload):

    url = os.environ['PITCHER_WEBHOOK_URL']

    resp = requests.post(url, json=payload)

    return json.dumps(resp.text)

@app.route('/')
def render_page():
    return app.send_static_file('index.html')

@app.route('/draft')
def render_draft_page():
    return app.send_static_file('draft.html')


@app.route('/espn_fantasy/get_closers')
def get_closers():

    closers = [el for el in _get_closers()]
    
    # TODO: write to database. if there are changes, send to Slack.
    # send_pitcher_webhook({"text": json.dumps(closers)})

    return json.dumps(closers)

def _get_closers():

    rp_types = set(["CLOSER", "NEXT_UP", "SETUP", "SLEEPER", "FUTURE", "LOOMING", "BATTLE", "COMMITTEE", "CO-CLOSERS"])
    errata = {
        28614: 30213,
        5064: 33089
    }

    repl_many = lambda w, z: reduce(lambda x, y: x.replace(y, ''), [w] + z)
    _clean = lambda x: x.replace(":", "").replace(" ", "_")
    url = 'http://sports.espn.go.com/fantasy/baseball/flb/story?page=REcloserorgchart'
    resp = requests.get(url).content
    soup = BeautifulSoup(resp)

    tbody = soup.find('table', attrs={'class': 'inline-table'}).find('tbody')

    rows = tbody.findAll('tr')

    # go through row groups
    row_group_size = 2
    for rx in xrange(len(rows)/row_group_size):
        team_codes = []
        for td in rows[rx*row_group_size].findAll('td'):
            if td.img:
                code = td.img['src'].split('/')[-1].split('.')[0]
                team_codes.append(code)

        row_group_contents = rows[rx*row_group_size+1].findAll('td')
        # go through columns
        for ix, team_code in enumerate(team_codes):

            team_contents = [el for el in row_group_contents[ix+1].children]

            rp_type = ''
            rps = []
            for child in team_contents:
                try:
                    clean_text = _clean(child.get_text())
                    if clean_text in rp_types:
                        if rps:
                            for rp in rps:
                                yield {
                                    "team_code": team_code,
                                    "role": rp_type,
                                    "player_id": rp[0] if rp[0] not in errata else errata[rp[0]],
                                    "player_name": rp[1]
                                }
                        rp_type = clean_text
                        rps = []
                    else:
                        if clean_text != '':
                            try:
                                player_id = int(child['href'].split('/')[-2])
                            # adapt to new category types:
                            except KeyError:
                                rp_types.add(clean_text)
                            player_name = child.get_text()
                            rps.append((player_id, player_name))

                except AttributeError:
                    continue

            # clear out whatever is left:
            if rps:
                for rp in rps:
                    yield {
                        "team_code": team_code,
                        "role": rp_type,
                        "player_id": rp[0] if rp[0] not in errata else errata[rp[0]],
                        "player_name": rp[1]
                    }


@app.route('/data_batting')
def query_db_batting():

    cursor = db_con.cursor(cursor_factory=RealDictCursor)
    query = 'SELECT * FROM sabrfilter_batting'
    cursor.execute(query)
    output = [dict(row) for row in cursor]
    payload = json.dumps(output)

    return payload

@app.route('/data_pitching')
def query_db_pitching():

    cursor = db_con.cursor(cursor_factory=RealDictCursor)
    query = 'SELECT * FROM sabrfilter_pitching'
    cursor.execute(query)
    output = [dict(row) for row in cursor]
    payload = json.dumps(output)

    return payload

@app.route('/get_config')
def get_config():

    config = {
        "version": 'v0.1.1'
    }

    return json.dumps(config)

if __name__ == "__main__":
    app.run()
