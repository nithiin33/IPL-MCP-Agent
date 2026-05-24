<div align="center">

# 🏏 IPL Text2SQL MCP Server

**Ask IPL cricket questions in plain English. Get answers from a full database.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-FastMCP-orange)](https://github.com/modelcontextprotocol)
[![LangChain](https://img.shields.io/badge/LangChain-SQL%20Toolkit-green)](https://langchain.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1--mini-412991?logo=openai&logoColor=white)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

*Powered by MCP · LangChain · LangGraph · SQLite*

</div>

---

## What is this?

**IPL Text2SQL MCP** is an agentic AI system that lets you query a full IPL cricket database using plain English. Type a question, and a ReAct agent automatically figures out the right SQL, runs it, and returns a clear answer — no SQL knowledge required.

```
"Who leads the 2026 Orange Cap right now?"
  → Abhishek Sharma (SRH) with 44 avg runs per match
```

The system is built on the **Model Context Protocol (MCP)**, which means the SQL tools are served as a standalone MCP server that any MCP-compatible client (Claude Desktop, custom agents, etc.) can connect to.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User (CLI)                        │
│              "Who won IPL 2025?"                     │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              ReAct Agent  (react_client.py)          │
│         GPT-4.1-mini + LangGraph + System Prompt     │
└───────────────────────┬─────────────────────────────┘
                        │  MCP over HTTP (streamable)
┌───────────────────────▼─────────────────────────────┐
│           MCP Server  (text2sql_server.py)           │
│          FastMCP · 4 SQL tools · port 8010           │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│        LangChain SQL Toolkit  ←→  SQLite             │
│               ipl_insights.db                        │
│    Team · Player · Season · Match · Batting · Bowling│
└─────────────────────────────────────────────────────┘
```

---

## Database Coverage

**19 seasons · 2008–2026 · 47 players · 10 franchises**

| Table | Rows (approx.) | Description |
|-------|---------------|-------------|
| `Team` | 10 | Franchises — CSK, MI, RCB, KKR, SRH, DC, RR, PBKS, GT, LSG |
| `Player` | 47 | Kohli, Rohit, Dhoni, Bumrah, Warner, Gayle, de Villiers and more |
| `Season` | 19 | Year, winner, runner-up, MVP, status (`Completed` / `In Progress`) |
| `Match` | ~1,200 | Venue, date, winner, win type/margin, Man of Match |
| `Batting` | ~16,000 | Runs, balls, fours, sixes, strike rate, dismissal type per innings |
| `Bowling` | ~7,000 | Overs, wickets, runs conceded, economy per innings |

### Schema Relationships

```
Season ──< Match >── Team
                 └── Player (ManOfMatch)
Match ──< Batting >── Player
      └── Bowling >── Player
Player >── Team (PrimaryTeam)
```

### Notable data points
- **2025:** RCB won maiden title, beat PBKS by 6 runs. Orange Cap: Sai Sudharsan (759 runs). Purple Cap: Prasidh Krishna (25 wickets).
- **2026:** Season in progress as of April 28 — Punjab Kings lead standings, ~40 matches played.
- **Historical:** All winners from Rajasthan Royals (2008) through KKR (2024) accurately mapped.

---

## MCP Tools

The server exposes four tools over HTTP that the ReAct agent calls autonomously:

| Tool | Input | Description |
|------|-------|-------------|
| `sql_db_list_tables` | *(none)* | List all tables in the database |
| `sql_db_schema` | `table_names` (comma-separated) | Schema + sample rows for given tables |
| `sql_db_query_checker` | `query` (SQL string) | Validate query before execution |
| `sql_db_query` | `query` (SQL SELECT) | Execute query and return results |

The agent follows a strict workflow: **list → schema → write SQL → check → execute → answer**.

---

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key

### 1. Clone

```bash
git clone https://github.com/sjsoumil/IPL-Text2SQL-MCP.git
cd IPL-Text2SQL-MCP
```

### 2. Install dependencies

```bash
pip install mcp langchain langchain-openai langchain-community \
            langchain-mcp-adapters langgraph python-dotenv
```

### 3. Set up environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your key:

```env
OPENAI_API_KEY=sk-...
DB_PATH=ipl_insights.db
PORT=8010
MCP_SERVER_URL=http://localhost:8010/mcp
```

### 4. Generate the database

```bash
python create_ipl_db.py
```

Output:
```
Season 2008 done  [Completed]
...
Season 2026 done  [In Progress]
  Team      :     10 rows
  Player    :     47 rows
  Season    :     19 rows
  Match     :  1,167 rows
  Batting   : 16,338 rows
  Bowling   :  7,002 rows

Created ipl_insights.db
```

### 5. Start the MCP server

```bash
python text2sql_server.py
```

```
Starting IPLText2SQLServer
  URL      : http://localhost:8010/mcp
  Database : ipl_insights.db
  Tools    : ['sql_db_list_tables', 'sql_db_schema', 'sql_db_query_checker', 'sql_db_query']
```

### 6. Run the interactive client

Open a second terminal:

```bash
python react_client.py
```

```
======================================================================
IPL Analytics Assistant (2008-2026)  |  type 'exit' to quit
======================================================================
Your question: _
```

---

## Example Questions

```
# Run scoring
Who are the top 5 run-scorers of all time in the IPL?
Show Virat Kohli's runs season by season.
Who has the highest strike rate among batters with 500+ runs?

# Wickets & bowling
Who took the most wickets in IPL 2025?
What is Jasprit Bumrah's average economy rate across all seasons?

# Teams & titles
Which team has won the most IPL titles?
Which team has the best win percentage in finals?

# Current season (2026)
Who leads the 2026 Orange Cap right now?
How many matches has Punjab Kings won so far in 2026?

# Records
Who has the most Man of the Match awards?
Which player has hit the most sixes in IPL history?
What is the biggest winning margin in IPL history?
```

---

## Project Structure

```
IPL-Text2SQL-MCP/
├── text2sql_server.py   # FastMCP server — exposes SQL tools over HTTP
├── react_client.py      # Interactive ReAct agent CLI
├── create_ipl_db.py     # Generates ipl_insights.db from scratch
├── .env.example         # Environment variable template
└── README.md
```

---

## How It Works

1. **User** types a natural-language question in the CLI.
2. **ReAct agent** (LangGraph + GPT-4.1-mini) reasons step-by-step, deciding which MCP tool to call next.
3. **MCP client** (`langchain-mcp-adapters`) forwards each tool call to the FastMCP server over HTTP.
4. **MCP server** delegates to LangChain's `SQLDatabaseToolkit` — which inspects the schema, validates the SQL, and executes it against SQLite.
5. Results flow back up the chain and the agent crafts a plain-English answer.

The agent is guided by a detailed system prompt that enforces safe SQL practices (SELECT only), handles ties correctly, and knows the full schema upfront to minimize unnecessary tool calls.

---

## Requirements

| Dependency | Purpose |
|------------|---------|
| `mcp` | MCP server runtime (FastMCP) |
| `langchain` | Core framework |
| `langchain-openai` | GPT-4.1-mini LLM |
| `langchain-community` | SQL database utilities |
| `langchain-mcp-adapters` | MCP ↔ LangChain tool bridge |
| `langgraph` | ReAct agent execution |
| `python-dotenv` | Environment variable loading |
