import datetime
import requests
import json
from bs4 import BeautifulSoup
import dateutil.parser as dup
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def _get_player_popup(fantasy_id):
    """Gets ESPN fantasy player overview popup using fantasyId
    returns BS4 Soup object"""

    base = 'http://games.espn.go.com/flb/format/playerpop/overview?'

    params = {
        "playerId": fantasy_id
    }

    resp = requests.get(base, params=params)

    soup = BeautifulSoup(resp.text)

    return soup

def converter(opts):
    """Converts ESPN playerId (from Fantasy tool) to statsId ()"""

    fantasy_id = opts.get('playerId')
    soup = _get_player_popup(fantasy_id)

    stats_id = soup.find(class_='pc').findAll('a')[1]['href'].split('=')[1]

    return int(stats_id)

class League():

    def __init__(self, league_id):
        self.league_id = league_id
        self.get_team_rosters()

    def get_rostered_players(self):
        base_url = 'http://games.espn.com/flb/leaguerosters'
        data = {'leagueId': self.league_id}
        r = requests.get(base_url, params=data)
        self.roster_url = r.url
        s = BeautifulSoup(r.content, 'html.parser')
        self.rostered_player_ids = {}
        self.team_ids = {}
        for table in s.find_all('table'):
            team = table.find('th').find('a')
            team_id = team['href'].split('=')[-1]
            team_name = team.get_text()
            for a in table.find_all('a', {'class': 'flexpop', 'leagueid': str(self.league_id)}):
                self.rostered_player_ids[a['playerid']] = {'team_id': team_id, 'team_name': team_name}

    def get_team_rosters(self):
        self.get_rostered_players()
        self.team_rosters = {}

        for player_id, data in self.rostered_player_ids.iteritems():
            team_id = data['team_id']
            team_roster = self.team_rosters.get('team_id', [])
            team_roster.append(player_id)

class Team():

    def __init__(self, league_id, team_id, year=2017):
        self.league_id = league_id
        self.team_id = team_id
        params = 'leagueId={0}&teamId={1}&seasonId={2}'.format(self.league_id, self.team_id, year)
        self.url = 'http://games.espn.com/flb/clubhouse?{}'.format(params)
        self.get_roster()

    def get_roster(self):
        league = League(self.league_id)
        self.roster = league.team_rosters[str(self.team_id)]


class FangraphsClosers():

    def __init__(self):
        self.get_fg_closers()

    def get_fg_closers(self):
        base_url = 'http://www.fangraphs.com/fantasy/category/bullpen-report/'
        r = requests.get(base_url)
        s = BeautifulSoup(r.content, 'html.parser')
        dates = []
        bullpen_reports = {}
        for h2 in s.find_all('h2', {'class': 'posttitle'}):
            try:
                br_date = dup.parse(h2.text, fuzzy=True)
                br_date_readable = br_date.strftime('%B %d, %Y')
                dates.append(br_date)
                bullpen_reports[br_date_readable] = h2.find('a')['href']
            except Exception:
                pass
        most_recent_br = max(dates)
        most_recent_br_readable = most_recent_br.strftime('%B %d, %Y')
        href = bullpen_reports[most_recent_br_readable]

        self.parse_closer_table(href)

    def parse_closer_table(self, url):
        r = requests.get(url)
        s = BeautifulSoup(r.content, 'html.parser')
        self.closer_table = []
        for td in s.find_all('td'):
            if td.get('class'):
                if ('closer' in td['class'][0].lower()) and (td.find('a')):
                    name = td.find('a').get_text()
                    player_url = td.find('a')['href']
                    player_id = player_url.split('?')[1].split('&')[0].split('=')[1]
                    role = td['class'][0].split('_')[0]
                    color = td['class'][0].split('_')[1]
                    player_dict = {'player_name': name, 'player_id': player_id, 'role': role, 'color': color}
                    self.closer_table.append(player_dict)


class GameScores():

    def __init__(self):
        self.get_game_scores()
        self.get_fg_team_stats()

    def get_latest_post(self):
        r = requests.get('http://www.espn.com/fantasy/baseball/')
        soup = BeautifulSoup(r.content, 'html.parser')
        daily_notes_dates = {}
        for a in soup.find_all('a'):
            if 'daily-notes' in a['href'].lower():
                date_string = a['href'].split('daily-notes-')[-1]
                date = dup.parse(date_string, fuzzy=True)
                daily_notes_dates[date] = a['href']
        self.latest_post = daily_notes_dates[max(daily_notes_dates.keys())]

    def get_game_scores(self):
        self.get_latest_post()
        url = 'http://www.espn.com{}'.format(self.latest_post)
        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'html.parser')
        self.game_scores = {}
        self.pitchers = {}
        self.venues = {}
        self.opponents = {}
        table = soup.find('table', {'class', 'inline-table'})
        self.date = dup.parse(table.find('caption').text, fuzzy=True)
        for tr in table.find_all('tr', {'class': 'last'}):
            try:
                player_id = tr.find('a')['href'].split('/')[-2:-1][0]
                game_score = tr.find('b').text
                name = tr.find('a').text
                team = tr.find('img')['src'].split('/')[-1].split('.')[0]
                opp = tr.find_all('b')[1].text
                if '@' in opp:
                    venue = opp.split('@')[1]
                    self.opponents[player_id] = opp.split('@')[1]
                else:
                    venue = team
                    self.opponents[player_id] = opp
                self.game_scores[player_id] = game_score
                self.pitchers[player_id] = name
                self.venues[player_id] = venue.lower()
            except TypeError:
                print('One of the table rows is missing a player href. Passing.')
                pass
        self.sorted_by_game_score = sorted(self.game_scores, key=self.game_scores.get, reverse=True)


    def get_park_factors(self):
        with open('./park_codes.json', 'r') as j:
            park_codes = json.load(j)
        park_factors_url = 'http://www.espn.com/mlb/stats/parkfactor/_/sort/HRFactor'
        r = requests.get(park_factors_url)
        s = BeautifulSoup(r.content, 'html.parser')
        park_factors = {}
        for a in s.find_all('a'):
            if 'http://espn.go.com/travel/stadium/index?eVenue=' in a.get('href'):
                hr_score = a.parent.parent.find('td', class_='sortcell').text
                park_factors[a.get('href').split('=')[1]] = hr_score
        self.park_factors = {}
        for i in self.pitchers.keys():
            self.park_factors[i] = park_factors.get(park_codes.get(self.venues.get(i)))
        logging.debug(self.park_factors)

    def get_fg_team_stats(self):
        self.get_park_factors()
        with open('./team_names.json', 'r') as j:
            team_names = json.load(j)
        logger.debug(team_names)
        fg_url = 'http://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=8&season=2017&month=0&season1=2017&ind=0&team=0,ts&rost=0&age=0&filter=&players=0&sort=16,d'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        session = requests.Session()
        r = session.post(fg_url, headers=headers)
        s = BeautifulSoup(r.content, 'html.parser')
        wrc_plus = {}
        for td in s.find_all('td', class_='rgSorted'):
            wrc_plus[td.parent.find('a').text.lower()] = td.text
        logging.debug('wrc_plus dict: {}'.format(wrc_plus))
        self.wrc_plus = {}
        for i in self.pitchers.keys():
            logging.info('getting team abbr')
            opp = self.opponents[i].lower()
            logging.debug(opp)
            logging.info("getting team name")
            team = team_names[opp]
            logging.debug(team)
            logging.info('getting wrc+ for team')
            self.wrc_plus[i] = wrc_plus[team]
            logging.debug(wrc_plus[team])

    def set_fantasy_team(self, ts_teams):
        self.ts_teams = ts_teams
