"""
Generates ipl_insights.db — a 6-table IPL database with data from all seasons (2008-2026).
2025: RCB won maiden title, beat PBKS by 6 runs. Orange Cap: Sai Sudharsan (759 runs).
2026: In progress as of April 28, 2026. ~40 matches played. Punjab Kings lead standings.
Tables mirror the relational pattern of the banking database:
  Team, Player, Season, Match, Batting, Bowling
Run once: python create_ipl_db.py
"""

import sqlite3
import random
from datetime import date, timedelta

random.seed(2024)

DB_PATH = "ipl_insights.db"

# ── DDL ──────────────────────────────────────────────────────────────────────

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Team (
    TeamID      INTEGER PRIMARY KEY,
    Name        TEXT    NOT NULL,
    ShortName   TEXT    NOT NULL,
    HomeCity    TEXT    NOT NULL,
    HomeGround  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS Player (
    PlayerID        INTEGER PRIMARY KEY,
    Name            TEXT    NOT NULL,
    Country         TEXT    NOT NULL,
    Role            TEXT    NOT NULL,       -- Batter / Bowler / All-rounder / WK-Batter
    BattingStyle    TEXT    NOT NULL,
    BowlingStyle    TEXT,
    PrimaryTeamID   INTEGER REFERENCES Team(TeamID)
);

CREATE TABLE IF NOT EXISTS Season (
    SeasonID     INTEGER PRIMARY KEY,
    Year         INTEGER NOT NULL UNIQUE,
    WinnerID     INTEGER REFERENCES Team(TeamID),   -- NULL if season still in progress
    RunnerUpID   INTEGER REFERENCES Team(TeamID),
    MVPID        INTEGER REFERENCES Player(PlayerID),
    TotalMatches INTEGER NOT NULL,
    Status       TEXT NOT NULL DEFAULT 'Completed'  -- 'Completed' or 'In Progress'
);

CREATE TABLE IF NOT EXISTS Match (
    MatchID         TEXT    PRIMARY KEY,   -- e.g. IPL2008_M01
    SeasonID        INTEGER NOT NULL REFERENCES Season(SeasonID),
    Team1ID         INTEGER NOT NULL REFERENCES Team(TeamID),
    Team2ID         INTEGER NOT NULL REFERENCES Team(TeamID),
    MatchDate       DATE    NOT NULL,
    Venue           TEXT    NOT NULL,
    WinnerID        INTEGER          REFERENCES Team(TeamID),
    WinType         TEXT,                  -- Runs / Wickets / Tie / No Result
    WinMargin       INTEGER,
    MatchType       TEXT    NOT NULL,      -- Group / Qualifier1 / Qualifier2 / Eliminator / Final
    ManOfMatchID    INTEGER          REFERENCES Player(PlayerID)
);

CREATE TABLE IF NOT EXISTS Batting (
    BattingID       INTEGER PRIMARY KEY AUTOINCREMENT,
    MatchID         TEXT    NOT NULL REFERENCES Match(MatchID),
    PlayerID        INTEGER NOT NULL REFERENCES Player(PlayerID),
    TeamID          INTEGER NOT NULL REFERENCES Team(TeamID),
    Runs            INTEGER NOT NULL DEFAULT 0,
    Balls           INTEGER NOT NULL DEFAULT 0,
    Fours           INTEGER NOT NULL DEFAULT 0,
    Sixes           INTEGER NOT NULL DEFAULT 0,
    StrikeRate      REAL    NOT NULL DEFAULT 0.0,
    IsOut           INTEGER NOT NULL DEFAULT 1,   -- 1 = out, 0 = not out
    DismissalType   TEXT                           -- Caught / Bowled / LBW / Run Out / Stumped / Not Out
);

CREATE TABLE IF NOT EXISTS Bowling (
    BowlingID       INTEGER PRIMARY KEY AUTOINCREMENT,
    MatchID         TEXT    NOT NULL REFERENCES Match(MatchID),
    PlayerID        INTEGER NOT NULL REFERENCES Player(PlayerID),
    TeamID          INTEGER NOT NULL REFERENCES Team(TeamID),
    Overs           REAL    NOT NULL DEFAULT 0.0,
    Maidens         INTEGER NOT NULL DEFAULT 0,
    RunsConceded    INTEGER NOT NULL DEFAULT 0,
    Wickets         INTEGER NOT NULL DEFAULT 0,
    Economy         REAL    NOT NULL DEFAULT 0.0
);
"""

# ── REFERENCE DATA ────────────────────────────────────────────────────────────

TEAMS = [
    (1,  "Chennai Super Kings",          "CSK",  "Chennai",   "MA Chidambaram Stadium"),
    (2,  "Mumbai Indians",               "MI",   "Mumbai",    "Wankhede Stadium"),
    (3,  "Royal Challengers Bengaluru",  "RCB",  "Bengaluru", "M. Chinnaswamy Stadium"),
    (4,  "Kolkata Knight Riders",        "KKR",  "Kolkata",   "Eden Gardens"),
    (5,  "Sunrisers Hyderabad",          "SRH",  "Hyderabad", "Rajiv Gandhi International Stadium"),
    (6,  "Delhi Capitals",               "DC",   "Delhi",     "Arun Jaitley Stadium"),
    (7,  "Rajasthan Royals",             "RR",   "Jaipur",    "Sawai Mansingh Stadium"),
    (8,  "Punjab Kings",                 "PBKS", "Mohali",    "PCA Stadium"),
    (9,  "Gujarat Titans",               "GT",   "Ahmedabad", "Narendra Modi Stadium"),
    (10, "Lucknow Super Giants",         "LSG",  "Lucknow",   "BRSABV Ekana Cricket Stadium"),
]

# (id, name, country, role, bat_style, bowl_style, team_id,
#  avg_bat_runs, avg_bat_balls, can_bowl, avg_bowl_wickets, avg_bowl_overs)
PLAYERS = [
    # ── Top-order batters / WKs ──
    (1,  "Virat Kohli",        "India",        "Batter",      "Right-hand bat", "Right-arm medium",       3,  35, 27, False, 0.0, 0),
    (2,  "Rohit Sharma",       "India",        "Batter",      "Right-hand bat", "Right-arm off-break",    2,  30, 24, False, 0.0, 0),
    (3,  "MS Dhoni",           "India",        "WK-Batter",   "Right-hand bat", None,                     1,  26, 18, False, 0.0, 0),
    (4,  "David Warner",       "Australia",    "Batter",      "Left-hand bat",  "Right-arm leg-break",    5,  38, 29, False, 0.0, 0),
    (5,  "Chris Gayle",        "West Indies",  "Batter",      "Left-hand bat",  "Right-arm off-break",    3,  43, 27, True,  0.2, 2),
    (6,  "AB de Villiers",     "South Africa", "Batter",      "Right-hand bat", "Right-arm medium",       3,  38, 23, False, 0.0, 0),
    (7,  "Suresh Raina",       "India",        "All-rounder", "Left-hand bat",  "Right-arm off-break",    1,  28, 22, True,  0.3, 2),
    (8,  "KL Rahul",           "India",        "WK-Batter",   "Right-hand bat", None,                     8,  38, 30, False, 0.0, 0),
    (9,  "Shikhar Dhawan",     "India",        "Batter",      "Left-hand bat",  "Right-arm off-break",    6,  33, 27, False, 0.0, 0),
    (10, "Shane Watson",       "Australia",    "All-rounder", "Right-hand bat", "Right-arm fast-medium",  7,  30, 22, True,  0.5, 3),
    (11, "Gautam Gambhir",     "India",        "Batter",      "Left-hand bat",  "Right-arm off-break",    4,  28, 23, False, 0.0, 0),
    (12, "Sachin Tendulkar",   "India",        "Batter",      "Right-hand bat", "Right-arm leg-break",    2,  31, 25, False, 0.0, 0),
    (13, "Yuvraj Singh",       "India",        "All-rounder", "Left-hand bat",  "Slow left-arm orthodox", 8,  27, 21, True,  0.3, 2),
    (14, "Rishabh Pant",       "India",        "WK-Batter",   "Left-hand bat",  None,                     6,  32, 22, False, 0.0, 0),
    (15, "Hardik Pandya",      "India",        "All-rounder", "Right-hand bat", "Right-arm fast-medium",  2,  28, 19, True,  0.9, 3.5),
    (26, "Jos Buttler",        "England",      "WK-Batter",   "Right-hand bat", None,                     7,  44, 30, False, 0.0, 0),
    (27, "Quinton de Kock",    "South Africa", "WK-Batter",   "Left-hand bat",  None,                     2,  33, 26, False, 0.0, 0),
    (28, "Faf du Plessis",     "South Africa", "Batter",      "Right-hand bat", "Right-arm medium",       3,  36, 27, False, 0.0, 0),
    (29, "Ruturaj Gaikwad",    "India",        "Batter",      "Right-hand bat", "Right-arm off-break",    1,  36, 28, False, 0.0, 0),
    (30, "Shubman Gill",       "India",        "Batter",      "Right-hand bat", "Right-arm off-break",    9,  36, 28, False, 0.0, 0),
    (31, "Sanju Samson",       "India",        "WK-Batter",   "Right-hand bat", None,                     7,  34, 24, False, 0.0, 0),
    (32, "Heinrich Klaasen",   "South Africa", "WK-Batter",   "Right-hand bat", None,                     5,  36, 21, False, 0.0, 0),
    (33, "Kieron Pollard",     "West Indies",  "All-rounder", "Right-hand bat", "Right-arm medium-fast",  2,  26, 16, True,  0.6, 3),
    (34, "Andre Russell",      "West Indies",  "All-rounder", "Right-hand bat", "Right-arm fast-medium",  4,  32, 17, True,  1.1, 3),
    (35, "Sunil Narine",       "West Indies",  "All-rounder", "Left-hand bat",  "Right-arm off-break",    4,  22, 13, True,  1.5, 4),
    # ── Specialist bowlers ──
    (16, "Lasith Malinga",     "Sri Lanka",    "Bowler",      "Right-hand bat", "Right-arm fast",         2,  5,  4,  True,  1.9, 4),
    (17, "Harbhajan Singh",    "India",        "Bowler",      "Right-hand bat", "Right-arm off-break",    2,  6,  5,  True,  1.4, 4),
    (18, "Jasprit Bumrah",     "India",        "Bowler",      "Right-hand bat", "Right-arm fast",         2,  5,  4,  True,  1.7, 4),
    (19, "Ravindra Jadeja",    "India",        "All-rounder", "Left-hand bat",  "Slow left-arm orthodox", 1,  22, 15, True,  1.2, 4),
    (20, "Dwayne Bravo",       "West Indies",  "All-rounder", "Right-hand bat", "Right-arm fast-medium",  1,  18, 13, True,  1.6, 4),
    (21, "Bhuvneshwar Kumar",  "India",        "Bowler",      "Right-hand bat", "Right-arm medium-fast",  5,  6,  5,  True,  1.4, 4),
    (22, "Amit Mishra",        "India",        "Bowler",      "Right-hand bat", "Right-arm leg-break",    6,  5,  4,  True,  1.3, 4),
    (23, "Pat Cummins",        "Australia",    "Bowler",      "Right-hand bat", "Right-arm fast",         4,  8,  6,  True,  1.5, 4),
    (24, "Ravichandran Ashwin","India",        "All-rounder", "Right-hand bat", "Right-arm off-break",    8,  12, 11, True,  1.3, 4),
    (25, "Yuzvendra Chahal",   "India",        "Bowler",      "Right-hand bat", "Right-arm leg-break",    7,  5,  4,  True,  1.6, 4),
    (36, "Trent Boult",        "New Zealand",  "Bowler",      "Right-hand bat", "Left-arm fast-medium",   2,  5,  4,  True,  1.5, 4),
    (37, "Kagiso Rabada",      "South Africa", "Bowler",      "Right-hand bat", "Right-arm fast",         6,  6,  5,  True,  1.6, 4),
    (38, "Mohammed Shami",     "India",        "Bowler",      "Right-hand bat", "Right-arm fast-medium",  9,  5,  4,  True,  1.4, 4),
    (39, "Rashid Khan",        "Afghanistan",  "All-rounder", "Right-hand bat", "Right-arm leg-break",    5,  10, 8,  True,  1.8, 4),
    (40, "Mitchell Starc",     "Australia",    "Bowler",      "Left-hand bat",  "Left-arm fast",          4,  6,  5,  True,  1.5, 4),
    # ── 2025 / 2026 players ──
    (41, "Sai Sudharsan",      "India",        "Batter",      "Left-hand bat",  "Right-arm off-break",    9,  40, 32, False, 0.0, 0),   # GT; Orange Cap 2025 (759 runs)
    (42, "Prasidh Krishna",    "India",        "Bowler",      "Right-hand bat", "Right-arm fast-medium",  9,  5,  4,  True,  1.6, 4),   # GT; Purple Cap 2025 (25 wkts)
    (43, "Suryakumar Yadav",   "India",        "Batter",      "Right-hand bat", "Right-arm medium",       2,  36, 22, False, 0.0, 0),   # MI; MVP 2025
    (44, "Abhishek Sharma",    "India",        "All-rounder", "Left-hand bat",  "Slow left-arm orthodox", 5,  44, 24, True,  0.5, 2),   # SRH; 141 off 55 vs PBKS; Orange Cap 2026 leader
    (45, "Vaibhav Sooryavanshi","India",       "Batter",      "Right-hand bat", "Right-arm off-break",    7,  38, 16, False, 0.0, 0),   # RR; 15-yr-old prodigy, SR 234+
    (46, "Eshan Malinga",      "Sri Lanka",    "Bowler",      "Right-hand bat", "Right-arm fast",         2,  4,  3,  True,  1.5, 4),   # Purple Cap co-leader 2026
    (47, "Jofra Archer",       "England",      "Bowler",      "Right-hand bat", "Right-arm fast",         2,  5,  4,  True,  1.5, 4),   # 13 wkts in 2026
]

# Real IPL season history
# (season_id, year, winner_team_id, runner_up_team_id, mvp_player_id, total_matches)
SEASONS = [
    (1,  2008, 7,  1,  10, 59),   # RR beat CSK; Shane Watson MVP
    (2,  2009, 5,  3,  4,  57),   # Deccan Chargers (mapped to SRH) beat RCB; Warner era begins
    (3,  2010, 1,  3,  3,  60),   # CSK beat RCB; Dhoni MVP
    (4,  2011, 1,  3,  6,  74),   # CSK beat RCB; AB de Villiers
    (5,  2012, 4,  1,  11, 76),   # KKR beat CSK; Gambhir MVP
    (6,  2013, 2,  1,  16, 76),   # MI beat CSK; Malinga MVP
    (7,  2014, 4,  8,  34, 60),   # KKR beat PBKS; Russell
    (8,  2015, 2,  1,  18, 59),   # MI beat CSK; Bumrah
    (9,  2016, 5,  3,  4,  60),   # SRH beat RCB; Warner Orange Cap (848 runs)
    (10, 2017, 2,  7,  15, 59),   # MI beat RR; Hardik Pandya
    (11, 2018, 1,  5,  19, 60),   # CSK beat SRH; Jadeja
    (12, 2019, 2,  1,  35, 60),   # MI beat CSK; Sunil Narine
    (13, 2020, 2,  6,  27, 60),   # MI beat DC; Quinton de Kock
    (14, 2021, 1,  4,  29, 60),   # CSK beat KKR; Ruturaj Gaikwad Orange Cap
    (15, 2022, 9,  7,  26, 74),   # GT beat RR; Jos Buttler Orange Cap
    (16, 2023, 1,  9,  1,  74),   # CSK beat GT; Virat Kohli
    (17, 2024, 4,    5,    32,   74),  # KKR beat SRH; Klaasen
    (18, 2025, 3,    8,    43,   74),  # RCB beat PBKS by 6 runs; SKY MVP; Orange: Sai Sudharsan 759; Purple: Prasidh Krishna 25
    (19, 2026, None, None, None, 40),  # In progress as of Apr-28-2026; PBKS leading table; ~40 matches played
]

# Venues per city
VENUES = {
    "Chennai":   "MA Chidambaram Stadium",
    "Mumbai":    "Wankhede Stadium",
    "Bengaluru": "M. Chinnaswamy Stadium",
    "Kolkata":   "Eden Gardens",
    "Hyderabad": "Rajiv Gandhi International Stadium",
    "Delhi":     "Arun Jaitley Stadium",
    "Jaipur":    "Sawai Mansingh Stadium",
    "Mohali":    "PCA Stadium",
    "Ahmedabad": "Narendra Modi Stadium",
    "Lucknow":   "BRSABV Ekana Cricket Stadium",
    "Pune":      "Maharashtra Cricket Association Stadium",
    "Dharamsala":"HPCA Stadium",
}

NEUTRAL_VENUES = ["Pune", "Dharamsala"]

# ── PLAYER LOOKUP ─────────────────────────────────────────────────────────────

player_data = {p[0]: p for p in PLAYERS}   # pid -> full tuple
team_data   = {t[0]: t for t in TEAMS}

# Each team's roster (players primarily associated with them)
TEAM_ROSTERS = {
    1:  [3, 7, 19, 20, 29, 10, 1],            # CSK
    2:  [2, 12, 16, 17, 18, 15, 27, 33, 36, 43, 46, 47],  # MI
    3:  [1, 5, 6, 28],                         # RCB
    4:  [11, 23, 34, 35, 40],                  # KKR
    5:  [4, 21, 32, 39, 44],                   # SRH
    6:  [9, 14, 22, 37],                       # DC
    7:  [10, 26, 25, 31, 45],                  # RR
    8:  [8, 13, 24],                           # PBKS
    9:  [30, 38, 15, 41, 42],                  # GT
    10: [8, 9],                                # LSG
}

# bowlers per team (guaranteed to bowl)
TEAM_BOWLERS = {
    1:  [19, 20, 10, 7],
    2:  [16, 17, 18, 15, 36, 33, 46, 47],
    3:  [5],
    4:  [23, 34, 35, 40],
    5:  [21, 39, 44],
    6:  [22, 37, 9],
    7:  [10, 25],
    8:  [13, 24],
    9:  [38, 42],
    10: [24, 22],
}

DISMISSAL_TYPES = ["Caught", "Bowled", "LBW", "Run Out", "Stumped"]

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def rand_batting(avg_runs, avg_balls, is_out):
    runs  = clamp(int(random.gauss(avg_runs, avg_runs * 0.6)), 0, 150)
    balls = clamp(int(random.gauss(avg_balls, avg_balls * 0.4)), max(1, runs), runs + 30)
    fours = clamp(int(runs * random.uniform(0.06, 0.16)), 0, runs // 4)
    sixes = clamp(int(runs * random.uniform(0.02, 0.12)), 0, runs // 6 + 1)
    sr    = round(runs / balls * 100, 2) if balls > 0 else 0.0
    dim   = random.choice(DISMISSAL_TYPES) if is_out else "Not Out"
    return runs, balls, fours, sixes, sr, dim

def rand_bowling(avg_wickets, avg_overs):
    overs    = round(clamp(random.gauss(avg_overs, 0.5), 1, 4), 1)
    wickets  = clamp(int(random.gauss(avg_wickets, 0.8)), 0, 4)
    runs_c   = clamp(int(random.gauss(overs * 8, overs * 2)), 0, int(overs * 18))
    maidens  = 1 if runs_c < int(overs) * 3 else 0
    economy  = round(runs_c / overs, 2) if overs > 0 else 0.0
    return overs, maidens, runs_c, wickets, economy


def build_match_batting(team_id, match_id, lineup_pids, conn):
    """Insert batting rows for one team's innings."""
    rows = []
    for idx, pid in enumerate(lineup_pids):
        p = player_data[pid]
        avg_r, avg_b = p[7], p[8]
        is_out = random.random() < 0.82 or idx == len(lineup_pids) - 1
        runs, balls, fours, sixes, sr, dim = rand_batting(avg_r, avg_b, bool(is_out))
        rows.append((match_id, pid, team_id, runs, balls, fours, sixes, sr, int(is_out), dim))
    conn.executemany(
        "INSERT INTO Batting(MatchID,PlayerID,TeamID,Runs,Balls,Fours,Sixes,StrikeRate,IsOut,DismissalType) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def build_match_bowling(team_id, match_id, bowler_pids, conn):
    """Insert bowling rows for one team's attack."""
    rows = []
    for pid in bowler_pids:
        p = player_data[pid]
        avg_w, avg_o = p[10], p[11]
        overs, maidens, runs_c, wickets, economy = rand_bowling(avg_w, avg_o)
        rows.append((match_id, pid, team_id, overs, maidens, runs_c, wickets, economy))
    conn.executemany(
        "INSERT INTO Bowling(MatchID,PlayerID,TeamID,Overs,Maidens,RunsConceded,Wickets,Economy) "
        "VALUES (?,?,?,?,?,?,?,?)", rows)


def get_lineup(team_id, n=7):
    """Return n player IDs from team roster; fill with generic players if short."""
    roster = list(TEAM_ROSTERS.get(team_id, []))
    random.shuffle(roster)
    while len(roster) < n:
        roster.append(random.choice(list(player_data.keys())))
    return roster[:n]


def get_bowlers(team_id, n=5):
    bowlers = list(TEAM_BOWLERS.get(team_id, []))
    random.shuffle(bowlers)
    while len(bowlers) < n:
        bowlers.append(random.choice([pid for pid, p in player_data.items() if p[9]]))
    return bowlers[:n]


def random_venue(team1_id, team2_id):
    city1 = team_data[team1_id][3]
    if random.random() < 0.5:
        city = city1
    else:
        city = random.choice(NEUTRAL_VENUES)
    return city, VENUES.get(city, "Unknown Stadium")


# ── SEASON SCHEDULE ───────────────────────────────────────────────────────────
# Teams that existed per season (some franchises added/removed over the years)
ACTIVE_TEAMS = {
    2008: [1,2,3,4,5,6,7,8],
    2009: [1,2,3,4,5,6,7,8],
    2010: [1,2,3,4,5,6,7,8],
    2011: [1,2,3,4,5,6,7,8],
    2012: [1,2,3,4,5,6,7,8],
    2013: [1,2,3,4,5,6,7,8],
    2014: [1,2,3,4,5,6,7,8],
    2015: [1,2,3,4,5,6,7,8],
    2016: [1,2,3,4,5,6,7,8],
    2017: [1,2,3,4,5,6,7,8],
    2018: [1,2,3,4,5,6,7,8],
    2019: [1,2,3,4,5,6,7,8],
    2020: [1,2,3,4,5,6,7,8],
    2021: [1,2,3,4,5,6,7,8],
    2022: [1,2,3,4,5,6,7,8,9,10],
    2023: [1,2,3,4,5,6,7,8,9,10],
    2024: [1,2,3,4,5,6,7,8,9,10],
    2025: [1,2,3,4,5,6,7,8,9,10],
    2026: [1,2,3,4,5,6,7,8,9,10],
}

def generate_matches(season_id, year, winner_id, runner_up_id, total_matches, conn):
    """
    Generate group-stage and (if complete) playoff matches for a season.
    For 2026 (in-progress): total_matches=40, all group stage, no playoffs yet.
    """
    teams = ACTIVE_TEAMS[year]
    match_counter = 0
    start_date = date(year, 3, 22)
    current_date = start_date

    # 2026 is still in progress — all 40 matches are group stage, no playoffs yet
    in_progress = (year == 2026)
    group_count = total_matches if in_progress else total_matches - 4

    # ── Group stage ──
    pairs = []
    for i in range(len(teams)):
        for j in range(i+1, len(teams)):
            pairs.append((teams[i], teams[j]))
    random.shuffle(pairs)

    for t1, t2 in pairs:
        if match_counter >= group_count:
            break
        match_counter += 1
        mid = f"IPL{year}_M{match_counter:02d}"
        _, venue = random_venue(t1, t2)
        winner = t1 if random.random() < 0.5 else t2
        win_type = random.choice(["Runs", "Wickets"])
        win_margin = random.randint(1, 8) if win_type == "Wickets" else random.randint(2, 55)

        lineup1 = get_lineup(t1)
        lineup2 = get_lineup(t2)
        mom = random.choice(lineup1 + lineup2)

        conn.execute(
            "INSERT INTO Match VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (mid, season_id, t1, t2, current_date.isoformat(), venue,
             winner, win_type, win_margin, "Group", mom)
        )
        build_match_batting(t1, mid, lineup1, conn)
        build_match_batting(t2, mid, lineup2, conn)
        build_match_bowling(t2, mid, get_bowlers(t2), conn)
        build_match_bowling(t1, mid, get_bowlers(t1), conn)
        current_date += timedelta(days=random.choice([1, 1, 2]))

    if in_progress:
        return   # 2026 season not yet complete — no playoffs

    # ── Playoffs (completed seasons only) ──
    playoffs = [
        (match_counter+1, "Qualifier1", runner_up_id, winner_id),
        (match_counter+2, "Eliminator",
         random.choice([t for t in teams if t not in (winner_id, runner_up_id)]),
         random.choice([t for t in teams if t not in (winner_id, runner_up_id)])),
        (match_counter+3, "Qualifier2", winner_id, runner_up_id),
        (match_counter+4, "Final",      winner_id, runner_up_id),
    ]
    for mnum, mtype, t1, t2 in playoffs:
        mid = f"IPL{year}_M{mnum:02d}"
        _, venue = random_venue(t1, t2)
        winner = winner_id if mtype == "Final" else (t1 if random.random() < 0.5 else t2)
        win_type = random.choice(["Runs", "Wickets"])
        win_margin = random.randint(1, 8) if win_type == "Wickets" else random.randint(2, 55)

        lineup1 = get_lineup(t1)
        lineup2 = get_lineup(t2)
        mom = random.choice(lineup1 + lineup2)

        conn.execute(
            "INSERT INTO Match VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (mid, season_id, t1, t2, current_date.isoformat(), venue,
             winner, win_type, win_margin, mtype, mom)
        )
        build_match_batting(t1, mid, lineup1, conn)
        build_match_batting(t2, mid, lineup2, conn)
        build_match_bowling(t2, mid, get_bowlers(t2), conn)
        build_match_bowling(t1, mid, get_bowlers(t1), conn)
        current_date += timedelta(days=3)


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)

    # Teams
    conn.executemany(
        "INSERT OR IGNORE INTO Team VALUES (?,?,?,?,?)", TEAMS)

    # Players
    conn.executemany(
        "INSERT OR IGNORE INTO Player(PlayerID,Name,Country,Role,BattingStyle,BowlingStyle,PrimaryTeamID) "
        "VALUES (?,?,?,?,?,?,?)",
        [(p[0],p[1],p[2],p[3],p[4],p[5],p[6]) for p in PLAYERS]
    )

    # Seasons + Matches
    for sid, year, winner, runner, mvp, total in SEASONS:
        status = "In Progress" if winner is None else "Completed"
        conn.execute(
            "INSERT OR IGNORE INTO Season VALUES (?,?,?,?,?,?,?)",
            (sid, year, winner, runner, mvp, total, status)
        )
        # For in-progress season use dummy IDs for scheduling; no playoffs generated
        generate_matches(sid, year, winner or 3, runner or 8, total, conn)
        print(f"  Season {year} done  [{status}]")

    conn.commit()
    conn.close()

    # Summary
    conn = sqlite3.connect(DB_PATH)
    for tbl in ["Team","Player","Season","Match","Batting","Bowling"]:
        (cnt,) = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
        print(f"  {tbl:10s}: {cnt:,} rows")
    conn.close()
    print(f"\nCreated {DB_PATH}")

if __name__ == "__main__":
    main()
