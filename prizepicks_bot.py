import os
import discord
from discord.ext import commands
import aiohttp
from datetime import datetime

# ============================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
BALLDONTLIE_API_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
# ============================================

LEAGUE_IDS = {
    "nba": 7,
    "nfl": 9,
    "mlb": 2,
    "nhl": 8,
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ============================================
# PRIZEPICKS
# ============================================
async def fetch_prizepicks(league_id=None):
    url = f"https://api.prizepicks.com/projections?league_id={league_id}&per_page=250&single_stat=true" if league_id else "https://api.prizepicks.com/projections?per_page=500&single_stat=true"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://prizepicks.com/",
        "Origin": "https://prizepicks.com",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else None


def parse_prizepicks(data):
    props = []
    if not data or "data" not in data:
        return props
    players = {}
    for item in data.get("included", []):
        if item.get("type") == "new_player":
            pid = item["id"]
            attrs = item.get("attributes", {})
            players[pid] = {
                "name": attrs.get("display_name", attrs.get("name", "Unknown")),
                "team": attrs.get("team", ""),
                "league": attrs.get("league", ""),
            }
    for proj in data["data"]:
        attrs = proj.get("attributes", {})
        player_id = proj.get("relationships", {}).get("new_player", {}).get("data", {}).get("id")
        player = players.get(player_id, {"name": "Unknown", "team": "", "league": ""})
        stat_type = attrs.get("stat_type", "")
        line = attrs.get("line_score", 0)
        league = attrs.get("league", player.get("league", ""))
        if stat_type and line:
            props.append({
                "player": player["name"],
                "team": player["team"],
                "league": league,
                "stat": stat_type,
                "line": float(line),
            })
    return props


# ============================================
# MLB STATS (Free Official API)
# ============================================
MLB_STAT_MAP = {
    "Pitcher Strikeouts": ("pitching", "strikeOuts"),
    "Strikeouts": ("pitching", "strikeOuts"),
    "Hits Allowed": ("pitching", "hits"),
    "Pitching Outs": ("pitching", "outs"),
    "Earned Runs Allowed": ("pitching", "earnedRuns"),
    "Walks Allowed": ("pitching", "baseOnBalls"),
    "Hits": ("hitting", "hits"),
    "Total Bases": ("hitting", "totalBases"),
    "Home Runs": ("hitting", "homeRuns"),
    "RBIs": ("hitting", "rbi"),
    "Runs Scored": ("hitting", "runs"),
    "Stolen Bases": ("hitting", "stolenBases"),
    "Batter Strikeouts": ("hitting", "strikeOuts"),
}

async def get_mlb_player_id(player_name):
    url = f"https://statsapi.mlb.com/api/v1/people/search?names={player_name.replace(' ', '+')}&sportId=1"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                people = data.get("people", [])
                if people:
                    return people[0]["id"], people[0]["fullName"]
    return None, None

async def get_mlb_stats(player_id, stat_group):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&season=2026&group={stat_group}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                stats_list = data.get("stats", [])
                if stats_list:
                    splits = stats_list[0].get("splits", [])
                    return splits[-10:] if splits else []
    return []


# ============================================
# NBA STATS (BallDontLie)
# ============================================
NBA_STAT_MAP = {
    "Points": "pts",
    "Rebounds": "reb",
    "Assists": "ast",
    "Steals": "stl",
    "Blocks": "blk",
    "Turnovers": "turnover",
    "3-PT Made": "fg3m",
    "Pts+Reb+Ast": "pts",
    "Pts+Ast": "pts",
    "Pts+Reb": "pts",
}

async def get_nba_player_id(player_name):
    headers = {"Authorization": BALLDONTLIE_API_KEY}
    url = f"https://api.balldontlie.io/v1/players?search={player_name.replace(' ', '%20')}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                players = data.get("data", [])
                if players:
                    p = players[0]
                    return p["id"], f"{p['first_name']} {p['last_name']}"
    return None, None

async def get_nba_stats(player_id):
    headers = {"Authorization": BALLDONTLIE_API_KEY}
    url = f"https://api.balldontlie.io/v1/stats?player_ids[]={player_id}&per_page=10&seasons[]=2024"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
    return []


# ============================================
# NHL STATS (Free Official API)
# ============================================
NHL_STAT_MAP = {
    "Goals": "goals",
    "Assists": "assists",
    "Points": "points",
    "Shots on Goal": "shots",
    "Blocked Shots": "blocked",
    "Power Play Points": "powerPlayPoints",
    "Saves": "saves",
    "Goals Against": "goalsAgainst",
}

async def get_nhl_player_id(player_name):
    url = f"https://api-web.nhle.com/v1/search?q={player_name.replace(' ', '+')}&type=player"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                players = data.get("players", [])
                if players:
                    p = players[0]
                    return p.get("playerId"), p.get("name", player_name)
    return None, None

async def get_nhl_stats(player_id):
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/20252026/2"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                games = data.get("gameLog", [])
                return games[-10:] if games else []
    return []


# ============================================
# EDGE CALCULATOR
# ============================================
def calc_hit_rate(values, line, over=True):
    if not values:
        return None, None
    hits = sum(1 for v in values if (v > line if over else v < line))
    hit_rate = round((hits / len(values)) * 100, 1)
    avg = round(sum(values) / len(values), 1)
    return hit_rate, avg

def get_trend(values, line, over=True):
    if len(values) < 3:
        return "➡️ Not enough data"
    recent = values[-3:]
    if over:
        if all(v > line for v in recent): return "🔥 Hot — hitting OVER last 3"
        if all(v < line for v in recent): return "❄️ Cold — missing OVER last 3"
    else:
        if all(v < line for v in recent): return "🔥 Hot — hitting UNDER last 3"
        if all(v > line for v in recent): return "❄️ Cold — missing UNDER last 3"
    return "➡️ Mixed results"

def confidence_label(hit_rate):
    if hit_rate >= 80: return "🔥 STRONG LEAN"
    elif hit_rate >= 65: return "✅ LEAN"
    elif hit_rate >= 50: return "⚠️ SLIGHT LEAN"
    else: return "❌ AVOID"


# ============================================
# COMMANDS
# ============================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and ready!")


@bot.command(name="pp")
async def prizepicks_lines(ctx, *, league: str = "MLB"):
    league_upper = league.upper()
    league_id = LEAGUE_IDS.get(league.lower())
    msg = await ctx.send(f"🔍 Fetching PrizePicks lines for **{league_upper}**...")
    data = await fetch_prizepicks(league_id)
    if not data:
        await msg.edit(content="❌ Could not fetch PrizePicks data.")
        return
    props = parse_prizepicks(data)
    filtered = [p for p in props if league_upper in p["league"].upper()] if not league_id else props
    if not filtered:
        await msg.edit(content=f"❌ No props found for **{league_upper}** right now.")
        return
    embed = discord.Embed(title=f"🎯 PrizePicks — {league_upper} Lines", color=discord.Color.purple(), timestamp=datetime.utcnow())
    embed.set_footer(text=f"{len(filtered)} props found")
    stat_groups = {}
    for prop in filtered:
        stat = prop["stat"]
        if stat not in stat_groups:
            stat_groups[stat] = []
        stat_groups[stat].append(prop)
    for stat, stat_props in list(stat_groups.items())[:5]:
        lines = [f"**{p['player']}** ({p['team']}) — {p['line']}" for p in stat_props[:6]]
        embed.add_field(name=f"📊 {stat}", value="\n".join(lines), inline=False)
    await msg.edit(content=None, embed=embed)


@bot.command(name="pplookup")
async def prizepicks_player(ctx, *, player_name: str):
    msg = await ctx.send(f"🔍 Looking up **{player_name}** on PrizePicks...")
    data = await fetch_prizepicks()
    if not data:
        await msg.edit(content="❌ Could not fetch PrizePicks data.")
        return
    all_props = parse_prizepicks(data)
    player_props = [p for p in all_props if player_name.lower() in p["player"].lower()]
    if not player_props:
        await msg.edit(content=f"❌ **{player_name}** not found on PrizePicks.")
        return
    embed = discord.Embed(
        title=f"🎯 {player_props[0]['player']} — PrizePicks Lines",
        color=discord.Color.purple(),
        description=f"Team: {player_props[0]['team']} | League: {player_props[0]['league']}"
    )
    lines = [f"**{prop['stat']}**: {prop['line']}" for prop in player_props]
    embed.add_field(name="📊 Current Lines", value="\n".join(lines), inline=False)
    await msg.edit(content=None, embed=embed)


@bot.command(name="edge")
async def edge_command(ctx, *, query: str):
    """
    !edge PlayerName | Stat | Over or Under
    Example: !edge Grant Holmes | Pitcher Strikeouts | Under
    Example: !edge LeBron James | Points | Over
    Example: !edge Connor McDavid | Goals | Over
    """
    parts = [p.strip() for p in query.split("|")]
    if len(parts) < 2:
        await ctx.send("❌ Format: `!edge PlayerName | Stat | Over or Under`\nExamples:\n`!edge Grant Holmes | Pitcher Strikeouts | Under`\n`!edge LeBron James | Points | Over`\n`!edge Connor McDavid | Goals | Over`")
        return

    player_name = parts[0]
    stat_name = parts[1]
    side = parts[2].lower().strip() if len(parts) > 2 else "over"
    over = "over" in side

    msg = await ctx.send(f"🔍 Analyzing **{player_name}** — {stat_name} {side.upper()}...")

    # Get PrizePicks line
    data = await fetch_prizepicks()
    all_props = parse_prizepicks(data) if data else []
    pp_prop = None
    for prop in all_props:
        if player_name.lower() in prop["player"].lower() and stat_name.lower() in prop["stat"].lower():
            pp_prop = prop
            break

    if not pp_prop:
        await msg.edit(content=f"❌ Could not find **{player_name} — {stat_name}** on PrizePicks right now.")
        return

    line = pp_prop["line"]
    league = pp_prop["league"].upper()
    values = []
    avg = None
    hit_rate = None
    actual_name = player_name

    # ---- MLB ----
    if league == "MLB":
        stat_info = MLB_STAT_MAP.get(stat_name)
        if stat_info:
            stat_group, stat_key = stat_info
            player_id, actual_name = await get_mlb_player_id(player_name)
            if player_id:
                game_logs = await get_mlb_stats(player_id, stat_group)
                for game in game_logs:
                    val = game.get("stat", {}).get(stat_key)
                    if val is not None:
                        try:
                            values.append(float(val))
                        except:
                            pass

    # ---- NBA ----
    elif league == "NBA":
        stat_key = NBA_STAT_MAP.get(stat_name)
        if stat_key and BALLDONTLIE_API_KEY:
            player_id, actual_name = await get_nba_player_id(player_name)
            if player_id:
                game_logs = await get_nba_stats(player_id)
                for game in game_logs:
                    val = game.get(stat_key)
                    if val is not None:
                        try:
                            values.append(float(val))
                        except:
                            pass

    # ---- NHL ----
    elif league == "NHL":
        stat_key = NHL_STAT_MAP.get(stat_name)
        if stat_key:
            player_id, actual_name = await get_nhl_player_id(player_name)
            if player_id:
                game_logs = await get_nhl_stats(player_id)
                for game in game_logs:
                    val = game.get(stat_key)
                    if val is not None:
                        try:
                            values.append(float(val))
                        except:
                            pass

    # ---- NFL ----
    elif league == "NFL":
        values = []  # NFL free stats limited — will show PP line only

    # Build embed
    hit_rate, avg = calc_hit_rate(values, line, over) if values else (None, None)

    embed = discord.Embed(
        title=f"📊 Edge Analysis — {pp_prop['player']}",
        color=discord.Color.green() if hit_rate and hit_rate >= 65 else discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="🎯 PrizePicks Line",
        value=f"**{stat_name} {side.upper()} {line}** | League: {league}",
        inline=False
    )

    if hit_rate is not None and values:
        trend = get_trend(values, line, over)
        confidence = confidence_label(hit_rate)
        recent_str = " → ".join([str(v) for v in values[-5:]])

        embed.add_field(
            name="📈 Historical Stats (Last 10 Games)",
            value=(
                f"Season avg: **{avg}** | Line: **{line}**\n"
                f"Hit rate {side.upper()}: **{hit_rate}%**\n"
                f"Last 5 games: {recent_str}\n"
                f"Trend: {trend}"
            ),
            inline=False
        )
        embed.add_field(
            name="💡 Recommendation",
            value=f"{confidence} **{side.upper()} {line}**",
            inline=False
        )
    else:
        embed.add_field(
            name="⚠️ Stats Unavailable",
            value=f"Could not find historical stats for **{player_name}** in {league}.\n{'NFL stats require a paid API.' if league == 'NFL' else 'Check the player name spelling.'}",
            inline=False
        )

    embed.set_footer(text="⚠️ For entertainment only. Gamble responsibly.")
    await msg.edit(content=None, embed=embed)


@bot.command(name="pphelp")
async def pp_help(ctx):
    embed = discord.Embed(title="🎯 PrizePicks Helper Commands", color=discord.Color.purple())
    embed.add_field(name="!pp MLB", value="Show PrizePicks lines (NBA, NFL, MLB, NHL)", inline=False)
    embed.add_field(name="!pplookup PlayerName", value="Look up a player\nExample: `!pplookup Shohei Ohtani`", inline=False)
    embed.add_field(
        name="!edge PlayerName | Stat | Over/Under",
        value=(
            "Analyze edge using historical stats\n"
            "MLB: `!edge Grant Holmes | Pitcher Strikeouts | Under`\n"
            "NBA: `!edge LeBron James | Points | Over`\n"
            "NHL: `!edge Connor McDavid | Goals | Over`"
        ),
        inline=False
    )
    await ctx.send(embed=embed)


bot.run(DISCORD_TOKEN)
