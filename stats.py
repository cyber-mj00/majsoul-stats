import asyncio
import aiohttp
import json
import os
import dotenv
import pandas as pd
import xlsxwriter
import datetime

from os.path import join, dirname

from mahjongsoul.helper import *
from mahjongsoul.manager import *

env_path = join(dirname(__file__), 'config.env')
dotenv.load_dotenv(env_path)
USE_MAJSOUL_TEAMS = True if int(os.environ.get('use_majsoul_teams')) == 1 else False

def readTeams(filename="teams.json"):
    with open(join(dirname(__file__), filename), encoding="utf-8") as f:
        teams = json.loads(f.read())
    return teams

def color_strtoint(color_str):
    try:
        assert len(color_str) == 6
    except:
        return -1, -1, -1
    return int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)

def main():
    print("Logging in to Majsoul Contest Dashboard...")
    hbr1_login = TournamentLogin(mjs_email=os.environ.get('mjs_email'), mjs_pw=os.environ.get('mjs_passwd'))
    print(f"Locating Contest {os.environ.get('contest_unique_id')}...")
    hbr1_manager = ContestManager(os.environ.get('contest_unique_id'), hbr1_login, "Heaven Burns Red")
    print("Contest found! Setting up...")
    hbr1_teams = Teams(os.environ.get('contest_unique_id'))
    hbr1_players = PlayerPool(os.environ.get('contest_unique_id'))
    hbr1_games = Games(os.environ.get('contest_unique_id'))
    print("Fetching teams list...")
    for team in (teams_list := hbr1_manager.get_teams()["list"]):
        print(f"Loading team {team['name']}")
        members = hbr1_manager.get_team_members(team_id=team["team_id"])["list"]
        hbr1_teams.addTeam(Team(team['team_id'], team['name'], [p['nickname'] for p in members], team['detail']))
        for m in members:
            m["account_data"] = json.loads(m["account_data"])
            hbr1_players.addPlayer(player := Player(m, team=team['name']))
            print(f"Added player {m['nickname']} to {team['name']}")
    
    print("Fetching game logs...")
    no_of_logs = int(hbr1_manager.get_logs()["total"])
    game_logs = hbr1_manager.get_logs(limit=no_of_logs+1)["record_list"]

    for game_record in game_logs:
        hbr1_games.addGameFromDict(game_record)
    
    print("Handling ties...")
    modifiers = hbr1_games.getModified()
    for p_nickname, modifier_list in modifiers.items():
        for modifier in modifier_list:
            hbr1_players.modifyPlayerPt(p_nickname, modifier["point"])
            hbr1_players.modifyPlayerRank(p_nickname, modifier["rank"])

    print("Generating spreadsheets...")
    #data_cols = ["队伍","选手","积分","试合数","平顺","1着","2着","3着","4着","TOP率","连对率","避四率","最高分"]
    df1 = pd.DataFrame(data=hbr1_players.exportToDict())
    df1 = df1.round({'平顺': 2, 'TOP率': 4, '连对率': 4, '避四率': 4})
    df2 = pd.DataFrame(data=hbr1_games.exportToDict())

    print("Generating individual stats")
    df1['队伍'] = pd.Categorical(df1['队伍'], [team['name'] for team in teams_list])
    df1_individual = df1.sort_values(by='积分', ascending=False).reset_index(drop=True)
    df1_individual.index = df1_individual.index + 1
    print("Generating team stats by player")
    df1_team = df1_individual.sort_values(by=['队伍', '积分'], ascending=[True, False]).reset_index(names='排名')
    print("Generating team scores")
    df1_teamTotal = df1_team.groupby('队伍', observed=True).agg({'积分': 'sum','试合数': 'sum','1着': 'sum','2着': 'sum','3着': 'sum','4着': 'sum'}).sort_values(by='积分', ascending=False).reset_index(names='队伍')
    df1_teamTotal.insert(2,"差值",-df1_teamTotal['积分'].diff())

    cutoff = df1_teamTotal['积分'].copy()
    cutoff.iloc[:6] = df1_teamTotal['积分'].iloc[:6] - df1_teamTotal.loc[6, '积分']
    cutoff.iloc[6:] = df1_teamTotal['积分'].iloc[6:] - df1_teamTotal.loc[5, '积分']
    df1_teamTotal.insert(3, "晋级线", cutoff)

    df1_teamTotal.index = df1_teamTotal.index + 1

    df1_individual.index.name = '排名'
    df1_teamTotal.index.name = '排名'

    print("Generating logs")
    df2 = pd.DataFrame(data=hbr1_games.exportToDict())
    df2.insert(3,"1位队伍",df2['1位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(7,"2位队伍",df2['2位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(11,"3位队伍",df2['3位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))
    df2.insert(15,"4位队伍",df2['4位玩家'].apply(lambda x: hbr1_teams.getPlayerTeam(x)))

    print("Writing to spreadsheet...")
    time_now = datetime.datetime.now(tz=(beijing_time := CNTZ()))
    ContrastColor = lambda r,g,b: "000000" if (0.299 * r + 0.587 * g + 0.114 * b)/255 > 0.5 else "ffffff"
    with pd.ExcelWriter((output_filename := os.environ.get('output_filename')+time_now.strftime("_%Y%m%d_%H%M%S")+".xlsx"), engine='xlsxwriter') as writer:
        df1_team.to_excel(writer, index=False, sheet_name='团体个人表', startrow=1)
        df1_individual.to_excel(writer, index=True, sheet_name='个人积分表', startrow=1)
        df1_teamTotal.to_excel(writer, index=True, sheet_name='队伍积分表', startrow=1)
        df2.to_excel(writer, index=False, sheet_name='牌谱数据')

        # Future step forward: automatic formatting
        formats = {}
        workbook = writer.book
        formats["score"] = workbook.add_format({"bg_color": "#FAF0CE", "font_color": "#000000"})
        formats["score_red"] = workbook.add_format({"bg_color": "#FAF0CE", "font_color": "#FF0000"})
        formats["simple_red"] = workbook.add_format({"font_color": "#FF0000"})
        formats["top"] = workbook.add_format({"bg_color": "#FF66CC", "font_color": "#000000"})
        formats["title"] = workbook.add_format({"bold": True, "align": "center"})
        formats["noteL"] = workbook.add_format({"bold": True, "align": "left"})
        formats["noteR"] = workbook.add_format({"bold": True, "align": "right"})
        for team in hbr1_teams.teams:
            r,g,b = color_strtoint(team_color := team.color)
            formats[team.name] = workbook.add_format({"bg_color": f"#{team_color}", "font_color": f"#{ContrastColor(r,g,b)}"})
        worksheet_individual = writer.sheets['个人积分表']
        worksheet_individual.set_column(1, 2, 30)
        worksheet_individual.set_column(6, 9, 6)

        worksheet_individual.merge_range("A1:N1", "炽焰天穹ML S1 2025  常规赛  个人成绩顺位表", formats["title"])
        row1, _ = df1_individual.shape
        worksheet_individual.merge_range(f"A{row1+3}:F{row1+3}", "★各选手出场数最少12个半庄、最多60个半庄", formats["noteL"])
        worksheet_individual.merge_range(f"G{row1+3}:N{row1+3}", f'{time_now.strftime("%m月%d日")} 终了时点', formats["noteR"])

        for team in hbr1_teams.teams:
            worksheet_individual.conditional_format(
                f"B3:C{row1+2}", {"type": "formula", "criteria": f'=$B3="{team.name}"', "format": formats[team.name]}
            )

        worksheet_individual.conditional_format(
            f"D3:D{row1+2}", {"type": "cell", "criteria": "<", "value": 0, "format": formats['score_red']}
        )
        worksheet_individual.conditional_format(
            f"D3:D{row1+2}", {"type": "cell", "criteria": ">=", "value": 0, "format": formats['score']}
        )
        worksheet_individual.conditional_format(
            f"G3:G{row1+2}", {"type": "top", "value": 1, "format": formats['top']}
        )
        worksheet_individual.conditional_format(
            f"K3:K{row1+2}", {"type": "top", "value": 1, "format": formats['top']}
        )
        worksheet_individual.conditional_format(
            f"L3:L{row1+2}", {"type": "top", "value": 1, "format": formats['top']}
        )
        worksheet_individual.conditional_format(
            f"M3:MG{row1+2}", {"type": "top", "value": 1, "format": formats['top']}
        )
        worksheet_individual.conditional_format(
            f"N3:N{row1+2}", {"type": "top", "value": 1, "format": formats['top']}
        )

        worksheet_team = writer.sheets['团体个人表']
        worksheet_team.set_column(1, 2, 30)
        worksheet_team.set_column(6, 9, 6)
        
        worksheet_team.merge_range("A1:N1", "炽焰天穹ML S1 2025  常规赛  个人成绩顺位表（按队伍）", formats["title"])
        row2, _ = df1_team.shape
        worksheet_team.merge_range(f"A{row2+3}:F{row2+3}", "★各选手出场数最少12个半庄、最多60个半庄", formats["noteL"])
        worksheet_team.merge_range(f"G{row2+3}:N{row2+3}", f'{time_now.strftime("%m月%d日")} 终了时点', formats["noteR"])

        for team in hbr1_teams.teams:
            worksheet_team.conditional_format(
                f"B3:C{row2+2}", {"type": "formula", "criteria": f'=$B3="{team.name}"', "format": formats[team.name]}
            )

        worksheet_team.conditional_format(
            f"D3:D{row2+2}", {"type": "cell", "criteria": "<", "value": 0, "format": formats['score_red']}
        )
        worksheet_team.conditional_format(
            f"D3:D{row2+2}", {"type": "cell", "criteria": ">=", "value": 0, "format": formats['score']}
        )

        worksheet_teamTotal = writer.sheets['队伍积分表']
        worksheet_teamTotal.set_column(1, 1, 30)
        worksheet_teamTotal.set_column(6, 9, 6)
        
        worksheet_teamTotal.merge_range("A1:J1", "炽焰天穹ML S1 2025  常规赛  队伍积分顺位表", formats["title"])
        row3, _ = df1_teamTotal.shape
        worksheet_teamTotal.merge_range(f"D{row3+3}:J{row3+3}", f'{time_now.strftime("%m月%d日")} 终了时点', formats["noteR"])

        for team in hbr1_teams.teams:
            worksheet_teamTotal.conditional_format(
                f"B3:B{row3+2}", {"type": "cell", "criteria": "==", "value": f'"{team.name}"', "format": formats[team.name]}
            )

        worksheet_teamTotal.conditional_format(
            f"C3:C{row3+2}", {"type": "cell", "criteria": "<", "value": 0, "format": formats['score_red']}
        )
        worksheet_teamTotal.conditional_format(
            f"C3:C{row3+2}", {"type": "cell", "criteria": ">=", "value": 0, "format": formats['score']}
        )
        worksheet_teamTotal.conditional_format(
            f"E3:E{row3+2}", {"type": "cell", "criteria": "<", "value": 0, "format": formats['simple_red']}
        )

        worksheet_paifu = writer.sheets['牌谱数据']
        worksheet_paifu.set_column(0, 1, 18)
        for i in range(2,17,4):
            worksheet_paifu.set_column(i, i+1, 20)
        row4, _ = df2.shape
        
        for team in hbr1_teams.teams:
            worksheet_paifu.conditional_format(
                f"C2:F{row4+1}", {"type": "formula", "criteria": f'=$D2="{team.name}"', "format": formats[team.name]}
            )
            worksheet_paifu.conditional_format(
                f"G2:J{row4+1}", {"type": "formula", "criteria": f'=$H2="{team.name}"', "format": formats[team.name]}
            )
            worksheet_paifu.conditional_format(
                f"K2:N{row4+1}", {"type": "formula", "criteria": f'=$L2="{team.name}"', "format": formats[team.name]}
            )
            worksheet_paifu.conditional_format(
                f"O2:R{row4+1}", {"type": "formula", "criteria": f'=$P2="{team.name}"', "format": formats[team.name]}
            )






if __name__ == "__main__":
    main()