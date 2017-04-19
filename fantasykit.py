import datetime
import requests
from bs4 import BeautifulSoup
import dateutil.parser as dup

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
            team_id = table.find('th').find('a')['href'].split('=')[-1]
            self.team_ids[team_id] = table.find('th').find('a').get_text()
            for a in table.find_all('a', {'class': 'flexpop', 'leagueid': str(self.league_id)}):
                self.rostered_player_ids[a['playerid']] = team_id

    def get_team_rosters(self):
        self.get_rostered_players()
        self.team_rosters = {}
        for p in self.rostered_player_ids:
            try:
                self.team_rosters[self.rostered_player_ids[p]].append(p)
            except KeyError:
                self.team_rosters[self.rostered_player_ids[p]] = []
                self.team_rosters[self.rostered_player_ids[p]].append(p)


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
        table = soup.find('table', {'class', 'inline-table'})
        for tr in table.find_all('tr', {'class': 'last'}):
            try:
                player_id = tr.find('a')['href'].split('/')[-2:-1][0]
                game_score = tr.find('b').text
                self.game_scores[player_id] = game_score
            except TypeError:
                print('One of the table rows is missing a player href. Passing.')
                pass
