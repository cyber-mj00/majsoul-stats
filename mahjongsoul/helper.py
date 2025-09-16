import asyncio
import json
import typing
import pandas as pd

from datetime import datetime, tzinfo, timedelta
from os.path import join, dirname

class CNTZ(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)
    def dst(self, dt):
        return timedelta(0)
    def tzname(self,dt):
        return "+08:00"
    def  __repr__(self):
        return f"{self.__class__.__name__}()"

class Player:
    def __init__(self, player_data):
        self.dyyId = None
        self.mjsId = player_data['player']['account_id']
        self.nickname = player_data['player']['nickname']
        self.team = ""
        self.total_game_count = player_data['player']['account_data']['total_game_count']
        self.games = player_data['player']['account_data']['recent_games']
        self.rank_pt = player_data['rank_data']['accumulate_point']
        self.rank_count = [player_data['rank_data']['rank_1_count'],
                           player_data['rank_data']['rank_2_count'],
                           player_data['rank_data']['rank_3_count'],
                           player_data['rank_data']['rank_4_count']]
    
    def setDyyId(self, dyyId):
        self.dyyId = dyyId
    
    def setTeam(self, team_name):
        self.team = team_name
    
    def getHighestGamePoints(self):
        start = 25000
        uma = [45000,5000,-15000,-35000]
        return max([game["total_point"]-uma[game["rank"]-1]+start for game in self.games]) if len(self.games) != 0 else 0
    
    def getTop(self):
        return (self.rank_count[0]) / self.total_game_count if self.total_game_count != 0 else 0
    
    def getRentai(self):
        return (self.rank_count[0]+self.rank_count[1]) / self.total_game_count if self.total_game_count != 0 else 0
    
    def get4thAvoidance(self):
        return (self.rank_count[0]+self.rank_count[1]+self.rank_count[2]) / self.total_game_count if self.total_game_count != 0 else 0
    
    def getAvgPlacement(self):
        return sum([a*b for a,b in zip([1,2,3,4], self.rank_count)]) / self.total_game_count if self.total_game_count != 0 else 0
    
    def __str__(self):
        return str({'nickname': self.nickname})
    
    def __repr__(self):
        return str({'_id': self.dyyId, 'mahjongSoulId': self.mjsId, 'nickname': self.nickname})

class PlayerPool:
    def __init__(self, contestId):
        self.contestId = contestId
        self.players: list[Player] = []
    
    def addPlayer(self, player: Player):
        self.players.append(player)
    
    def addPlayerFromDict(self, player_data):
        self.players.append(Player(player_data))
    
    def assignPlayerToTeam(self, nickname, team_name):
        try:
            idx = [p.nickname for p in self.players].index(nickname)
            self.players[idx].setTeam(team_name)
        except ValueError as e:
            print("Player not found.")
    
    def exportToDict(self):
        data_cols = ["队伍","选手","积分","试合数","平顺","1着","2着","3着","4着","TOP率","连对率","避四率","最高分"]
        data = {a: [] for a in data_cols}

        for player in self.players:
            data["队伍"].append(player.team)
            data["选手"].append(player.nickname)
            data["积分"].append(player.rank_pt / 1000)
            data["试合数"].append(player.total_game_count)
            data["平顺"].append(player.getAvgPlacement())
            data["1着"].append(player.rank_count[0])
            data["2着"].append(player.rank_count[1])
            data["3着"].append(player.rank_count[2])
            data["4着"].append(player.rank_count[3])
            data["TOP率"].append(player.getTop())
            data["连对率"].append(player.getRentai())
            data["避四率"].append(player.get4thAvoidance())
            data["最高分"].append(player.getHighestGamePoints())
        
        return data


class Team:
    def __init__(self, dyyId, name, players, color=None):
        self.dyyId = dyyId
        self.name = name
        self.players: list[str] = players
        self.color = color
    
    def inTeam(self, nickname):
        return nickname in self.players

    def __str__(self):
        return str({"name": self.name, "players": self.players})
    
    def __repr__(self):
        return str({"_id": self.dyyId, "name": self.name, "players": self.players, "color": self.color})

class Teams:
    def __init__(self, contestId):
        self.contestId = contestId
        self.teams: list[Team] = []
    
    def addTeam(self, team: Team):
        self.teams.append(team)
    
    def getPlayerTeam(self, nickname):
        for t in self.teams:
            if t.inTeam(nickname):
                return t.name
        return ""

class Game:
    def __init__(self, game_data):
        self.uuid = game_data['uuid']
        self.players = self.__addPlayers(game_data)
        self.start_time = game_data['start_time']
        self.end_time = game_data['end_time']
    
    def __addPlayers(self,game_data):
        account = sorted(game_data['accounts'], key=lambda x:x['seat'])
        for j,k in zip([0,1,2],[1,2,3]):
            # Share points in case of tie
            if game_data['result']['players'][j]["part_point_1"] == game_data['result']['players'][k]["part_point_1"]:
                new_point = (game_data['result']['players'][j]["total_point"]+game_data['result']['players'][k]["total_point"]) / 2
                game_data['result']['players'][j]["total_point"] = new_point
                game_data['result']['players'][k]["total_point"] = new_point
        for i in range(4):
            result = [p for p in game_data['result']['players'] if p['seat'] == i][0]
            account[i]["part_point_1"] = result["part_point_1"]
            account[i]["total_point"] = result["total_point"]
        return account
    
    def getPlayerData(self, nickname):
        return [p for p in self.players if p['nickname'] == nickname]
    
    def hasPlayed(self, nickname):
        return len([p for p in self.players if p['nickname'] == nickname]) == 1

class Games:
    def __init__(self, contestId):
        self.contestId = contestId
        self.game_list: list[Game] = []
    
    def addGame(self, game: Game):
        self.game_list.append(game)
    
    def addGameFromDict(self, game_data):
        self.game_list.append(Game(game_data))
    
    def getGameFromUuid(self, uuid):
        return [g for g in self.game_list if g.uuid == uuid]
    
    def getPlayerGames(self, nickname):
        return [g for g in self.game_list if g.hasPlayed(nickname)]
    
    def exportToDict(self):
        data_cols = ["开始时间","结束时间", "1位玩家","1位分数","1位终局点数","2位玩家","2位分数","2位终局点数","3位玩家","3位分数","3位终局点数","4位玩家","4位分数","4位终局点数","牌谱链接"]
        data = {a: [] for a in data_cols}
        beijing_time = CNTZ()

        for game in self.game_list:
            game_data = sorted(game.players, key=lambda x:x["total_point"], reverse=True)
            data["开始时间"].append(datetime.fromtimestamp(game.start_time, tz=beijing_time).strftime("%Y-%m-%d %H:%M:%S"))
            data["结束时间"].append(datetime.fromtimestamp(game.end_time, tz=beijing_time).strftime("%Y-%m-%d %H:%M:%S"))
            data["1位玩家"].append(game_data[0]["nickname"])
            data["1位分数"].append(game_data[0]["part_point_1"])
            data["1位终局点数"].append(game_data[0]["total_point"] / 1000)
            data["2位玩家"].append(game_data[1]["nickname"])
            data["2位分数"].append(game_data[1]["part_point_1"])
            data["2位终局点数"].append(game_data[1]["total_point"] / 1000)
            data["3位玩家"].append(game_data[2]["nickname"])
            data["3位分数"].append(game_data[2]["part_point_1"])
            data["3位终局点数"].append(game_data[2]["total_point"] / 1000)
            data["4位玩家"].append(game_data[3]["nickname"])
            data["4位分数"].append(game_data[3]["part_point_1"])
            data["4位终局点数"].append(game_data[3]["total_point"] / 1000)
            data["牌谱链接"].append("https://game.maj-soul.com/1/?paipu="+game.uuid)
        
        return data
             
#datetime.fromtimestamp(timestamp, tz=None)