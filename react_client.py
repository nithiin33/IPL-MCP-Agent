import asyncio
import os
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
from openai import RateLimitError

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8010/mcp")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

SYSTEM_INSTRUCTIONS = """You are an expert IPL cricket analytics assistant with access to a
SQLite database covering all IPL seasons from 2008 to 2026.

DATABASE SCHEMA:
- Team(TeamID, Name, ShortName, HomeCity, HomeGround)
    10 IPL franchises: CSK, MI, RCB, KKR, SRH, DC, RR, PBKS, GT, LSG

- Player(PlayerID, Name, Country, Role, BattingStyle, BowlingStyle, PrimaryTeamID)
    Role values: 'Batter', 'Bowler', 'All-rounder', 'WK-Batter'
    47 players including Kohli, Rohit, Dhoni, Warner, Gayle, de Villiers, Bumrah, Malinga, etc.

- Season(SeasonID, Year, WinnerID, RunnerUpID, MVPID, TotalMatches, Status)
    Status: 'Completed' or 'In Progress'
    2025: RCB beat PBKS (Status=Completed)
    2026: Status='In Progress' — WinnerID and RunnerUpID are NULL

- Match(MatchID, SeasonID, Team1ID, Team2ID, MatchDate, Venue, WinnerID, WinType, WinMargin, MatchType, ManOfMatchID)
    MatchType: 'Group', 'Qualifier1', 'Qualifier2', 'Eliminator', 'Final'
    WinType: 'Runs' or 'Wickets'
    MatchID format: 'IPL2024_M01'

- Batting(BattingID, MatchID, PlayerID, TeamID, Runs, Balls, Fours, Sixes, StrikeRate, IsOut, DismissalType)
    IsOut: 1 = out, 0 = not out
    DismissalType: 'Caught', 'Bowled', 'LBW', 'Run Out', 'Stumped', 'Not Out'

- Bowling(BowlingID, MatchID, PlayerID, TeamID, Overs, Maidens, RunsConceded, Wickets, Economy)

KEY JOINS:
- Player stats by season: Batting/Bowling → Match (MatchID) → Season (SeasonID)
- Player info: Batting/Bowling → Player (PlayerID)
- Team info: Batting/Bowling → Team (TeamID)
- Season winners: Season → Team (WinnerID / RunnerUpID)
- Man of Match: Match → Player (ManOfMatchID)

WORKFLOW (follow this exact order every time):
1. Call sql_db_list_tables ONCE at the start to confirm available tables.
2. Call sql_db_schema for tables relevant to the question.
3. Write a SQL query to answer the question.
4. Call sql_db_query_checker to validate the query.
5. Call sql_db_query to execute it and return results.
6. Present findings in clear, natural language.

STRICT RULES:
- Call sql_db_list_tables ONLY ONCE per turn.
- NEVER show SQL to the user — it is internal only.
- NEVER generate INSERT, UPDATE, DELETE, or DROP statements.
- Use LIMIT 10 unless the user specifies otherwise.
- For season filtering: JOIN to Season table and filter on Season.Year.
- For date filtering on MatchDate: strftime('%Y', MatchDate) = '2025'
- Bowling average = RunsConceded / Wickets (only when Wickets > 0).
- Strike rate = ROUND(Runs * 100.0 / NULLIF(Balls, 0), 2).
- Economy = ROUND(RunsConceded * 1.0 / NULLIF(Overs, 0), 2).
- If WinnerID IS NULL in Season, that season is still in progress — say so clearly.
- If a query returns no rows, state that clearly; do not guess.
- Always JOIN across tables when the question spans entities.
- TIES: When a question asks for "most", "highest", "best", or "top 1" of something,
  ALWAYS check for ties. Use a HAVING clause to find all entries that share the maximum:
    HAVING COUNT(*) = (SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM ... GROUP BY ...))
  Never silently drop tied entries — if two or more share the top value, name all of them.

Your final response must be grounded entirely in the database results.
"""


async def run_query(agent, query: str, max_steps: int = 15) -> str:
    """Run a single natural-language query through the ReAct agent with retry logic."""
    messages = [HumanMessage(content=query)]
    tool_call_counts: dict = {}
    event = None
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            async for event in agent.astream(
                input={"messages": messages},
                config={"recursion_limit": max_steps},
                stream_mode="values",
            ):
                if not event or "messages" not in event:
                    continue

                last_message = event["messages"][-1]

                if type(last_message).__name__ == "AIMessage":
                    for tc in getattr(last_message, "tool_calls", []):
                        call_key = f"{tc['name']}:{tc.get('args', '')}"
                        tool_call_counts[call_key] = tool_call_counts.get(call_key, 0) + 1
                        if tool_call_counts[call_key] >= 3:
                            return "Error: Detected repeated tool call — the agent is stuck in a loop."

            if event and "messages" in event:
                final = event["messages"][-1]
                if hasattr(final, "content"):
                    return str(final.content)

            return "No response generated."

        except RateLimitError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff: 2, 4, 8 seconds
                print(f"\nRate limited. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                return f"Error: Rate limit exceeded. Your OpenAI quota may be exhausted. Please check your billing: https://platform.openai.com/account/billing/overview"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error during query: {str(e)}"
    
    return "Failed after retries"


async def main():
    mcp_servers = {
        "ipl": {
            "url": MCP_SERVER_URL,
            "transport": "streamable_http",
        }
    }

    print("Connecting to IPL MCP server...")
    try:
        client = MultiServerMCPClient(mcp_servers)
        tools = await client.get_tools()
        print(f"Connected! Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}: {tool.description}")
    except Exception as e:
        print(f"\nFailed to connect to MCP server: {str(e)}")
        print("Make sure the server is running: python text2sql_server.py")
        return

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_INSTRUCTIONS),
        ("placeholder", "{messages}"),
    ])

    agent = create_react_agent(llm, tools, prompt=prompt)
    print("\nAgent ready.\n")
    print("⚠️  If you get rate limit errors, check your OpenAI billing:")
    print("   https://platform.openai.com/account/billing/overview\n")

    print("="*70)
    print("IPL Analytics Assistant (2008-2026)  |  type 'exit' to quit")
    print("="*70)
    print("\nExample questions:")
    print("  - Who are the top 5 run-scorers of all time in the IPL?")
    print("  - Which team has won the most IPL titles?")
    print("  - Who leads the 2026 Orange Cap right now?")
    print("  - Show Virat Kohli's runs season by season.")
    print("  - Who took the most wickets in IPL 2025?")
    print()

    while True:
        try:
            query = input("Your question: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            result = await run_query(agent, query)
            print(f"\n{result}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    asyncio.run(main())
