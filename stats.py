import asyncio
import aiohttp
import json
import os
import dotenv
import pandas as pd
import xlsxwriter

from os.path import join, dirname

from mahjongsoul.helper import *
from mahjongsoul.manager import *

env_path = join(dirname(__file__), 'config.env')
dotenv.load_dotenv(env_path)

def readTeams(filename="teams.json"):
    with open(join(dirname(__file__), filename), encoding="utf-8") as f:
        teams = json.loads(f.read())
    return teams


def main():
    print("Logging in to Majsoul Contest Dashboard...")
    hbr1_login = TournamentLogin(mjs_email=os.environ.get('mjs_email'), mjs_pw=os.environ.get('mjs_passwd'))
    print(f"Locating Contest {os.environ.get('contest_unique_id')}...")
    hbr1_manager = ContestManager(os.environ.get('contest_unique_id'), hbr1_login, "Heaven Burns Red")
    print("Contest found! Setting up...")
    teams_list = readTeams()
    hbr1_teams = Teams(os.environ.get('contest_unique_id'))
    hbr1_players = PlayerPool(os.environ.get('contest_unique_id'))
    hbr1_games = Games(os.environ.get('contest_unique_id'))
    for team in teams_list:
        hbr1_teams.addTeam(Team(team['_id'], team['name'], [p['nickname'] for p in team['players']], team['color']))

    print("Fetching players list...")
    no_of_players = int(hbr1_manager.get_all_players_stats_card()["total"])
    players_list = hbr1_manager.get_all_players_stats_card(limit=no_of_players+1)["list"]
    
    for account_id in [p['account_id'] for p in players_list]:
        print(f"Fetching player {account_id}...")
        player_detail = hbr1_manager.get_player_stats_card(account_id)
        player = Player(player_detail)
        player.setTeam(hbr1_teams.getPlayerTeam(player_detail['player']['nickname']))
        hbr1_players.addPlayer(player)
    
    print("Fetching game logs...")
    no_of_logs = int(hbr1_manager.get_logs()["total"])
    game_logs = hbr1_manager.get_logs(limit=no_of_logs+1)["record_list"]

    for game_record in game_logs:
        hbr1_games.addGameFromDict(game_record)

    print("Generating spreadsheets...")
    data_cols = ["队伍","选手","积分","试合数","平顺","1着","2着","3着","4着","TOP率","连对率","避四率","最高分"]
    df1 = pd.DataFrame(data=hbr1_players.exportToDict())
    df2 = pd.DataFrame(data=hbr1_games.exportToDict())

    print("Generating individual stats")
    df1['队伍'] = pd.Categorical(df1['队伍'], [team['name'] for team in teams_list])
    df1_individual = df1.sort_values(by='积分', ascending=False).reset_index(drop=True)
    df1_individual.index = df1_individual.index + 1
    print("Generating team stats by player")
    df1_team = df1_individual.sort_values(by=['队伍', '积分'], ascending=[True, False]).reset_index(names='排名')
    print("Generating team scores")
    df1_teamTotal = df1_team.groupby('队伍', observed=True).agg({'积分': 'sum','试合数': 'sum','1着': 'sum','2着': 'sum','3着': 'sum','4着': 'sum'}).sort_values(by='积分', ascending=False).reset_index(names='队伍')
    df1_teamTotal.insert(2,"差值",df1_teamTotal['积分'].diff())
    df1_teamTotal.insert(3,"晋级线",df1_teamTotal['积分']-df1_teamTotal.loc[5,'积分'])
    df1_teamTotal.index = df1_teamTotal.index + 1

    print("Generating logs")
    df2 = pd.DataFrame(data=hbr1_games.exportToDict())
    df2.insert(3,"1位队伍",df2['1位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(7,"2位队伍",df2['2位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(11,"3位队伍",df2['3位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(15,"4位队伍",df2['4位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))

    print("Writing to spreadsheet...")
    with pd.ExcelWriter(os.environ.get('output_filename'), engine='xlsxwriter') as writer:
        df1_individual.to_excel(writer, index=True, sheet_name='个人积分表')
        df1_team.to_excel(writer, index=False, sheet_name='团体个人表')
        df1_teamTotal.to_excel(writer, index=True, sheet_name='队伍积分表')
        df2.to_excel(writer, index=False, sheet_name='牌谱数据')

        # Future step forward: automatic formatting
        #workbook = writer.book
        #worksheet_individual = writer.sheets['个人积分表']
        #worksheet_team = writer.sheets['团体个人表']
        #worksheet_teamTotal = writer.sheets['队伍积分表']
        #worksheet_paifu = writer.sheets['牌谱数据']







if __name__ == "__main__":
    main()