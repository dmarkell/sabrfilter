
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

    return json.dumps(closers)


@app.route('/espn_fantasy/update_closers')
def update_closers():

    rps = [i for i in _get_closers()] # list of dictionaries
    new_table = [(k['player_id'], k['role'], k['player_name'], k['team_code']) for k in rps] # list of tuple, in order to perform set logic with cur.fetchall

    cur = db_con.cursor()
    cur.execute('SELECT player_id, role, player_name, team_code FROM closers;')
    old_table = cur.fetchall()
    old_table_dict = {i[0]: {'role': i[1], 'player_name': i[2], 'team_code': i[3]} for i in old_table} # create dict from list of tuples for fast lookups

    # set logic to get changes
    roles_changed = list(set(new_table).difference(set(old_table))) # records in ESPN closer table but not pg table
    roles_dropped = list(set(old_table).difference(set(new_table))) # records in pg table but not ESPN closer table

    closer_changes = []
    for i in roles_changed:
        try:
            notification = '{0} ({1}) was {2} but is now {3}'.format(i[2], i[3], old_table_dict.get(i[0]).get('role'), i[1])
        except AttributeError: # Attribute error thrown if closer not already in pg table
            notification = '{0} ({1}) is now {2}'.format(i[2], i[3], i[1])
        closer_changes.append(notification)
        if i[0] in [k for k in old_table_dict]:
            update_closer(i)
        else:
            insert_closer(i)

    for i in [j for j in roles_dropped if j[0] not in [k[0] for k in roles_changed]]:
        if i[1] is not None: # should now only be instances where pg shows active role for closer, but closer is no longer in ESPN table
            notification = '{0} ({1}) was {2} but has been removed from the ESPN closer table'.format(i[2], i[3], i[1])
            closer_changes.append(notification)
            update_closer(i, flush_role=True)

    if len(closer_changes) > 0:
        for notification in set(closer_changes):
            payload = {'text': notification}
            send_pitcher_webhook(payload)

    return json.dumps(list(set(closer_changes)))


def update_closer(rp, flush_role=False):

    cur = db_con.cursor()
    if flush_role == True:
        role = None
    else:
        role = rp[1]
    cur.execute('UPDATE closers SET player_name=%s, role=%s, team_code=%s WHERE player_id=%s;', (rp[2], role, rp[3], rp[0]))
    db_con.commit()


def insert_closer(rp):

    cur = db_con.cursor()
    cur.execute('INSERT INTO closers(player_id, role, player_name, team_code) VALUES(%s, %s, %s, %s);', (rp[0], rp[1], rp[2], rp[3]))
    db_con.commit()


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
    soup = BeautifulSoup(resp, 'html.parser')

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
