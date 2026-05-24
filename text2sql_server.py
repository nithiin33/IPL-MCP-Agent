from mcp.server.fastmcp import FastMCP
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv
import os
import traceback
import sqlite3
import asyncio
import time

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ipl_insights.db")
PORT = int(os.getenv("PORT", "8010"))

if not os.path.exists(DB_PATH):
    print(f"WARNING: Database not found at {DB_PATH}")
    print("Run: python create_ipl_db.py")
else:
    print(f"Database found at {DB_PATH}")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

# Simple tool implementations to avoid langchain toolkit compatibility issues
def get_db_connection():
    return sqlite3.connect(DB_PATH)

print(f"Database initialized successfully")

mcp = FastMCP(
    name="IPLText2SQLServer",
    instructions=(
        "IPL cricket analytics database covering all seasons 2008-2026. "
        "Tables: Team, Player, Season, Match, Batting, Bowling. "
        "Use the tools to list tables, inspect schemas, validate and execute SQL queries "
        "to answer questions about IPL players, teams, matches, and statistics."
    ),
    port=PORT,
)


@mcp.tool()
async def sql_db_list_tables(tool_input: str = "") -> str:
    """List all available tables in the IPL database."""
    try:
        result = db.get_table_names()
        tables_str = ", ".join(result) if result else "No tables found"
        print(f"[list_tables] {tables_str}")
        return tables_str
    except Exception as e:
        error = f"Error listing tables: {str(e)}"
        print(f"[ERROR] {error}")
        traceback.print_exc()
        return error


@mcp.tool()
async def sql_db_schema(table_names: str) -> str:
    """
    Get the schema and sample rows for one or more tables.
    Input: comma-separated table names, e.g. "Batting, Player"
    Output: column definitions and sample rows for each table
    """
    try:
        cleaned = table_names.strip()
        print(f"[schema] Fetching schema for: '{cleaned}'")
        # Use LangChain's built-in method to get table info
        result = db.get_table_info(cleaned.split(","))
        result_str = str(result)
        print(f"[schema] Returned {len(result_str)} chars")
        return result_str
    except Exception as e:
        error = f"Error getting schema: {str(e)}"
        print(f"[ERROR] {error}")
        traceback.print_exc()
        return error


@mcp.tool()
async def sql_db_query_checker(query: str) -> str:
    """
    Validate SQL query syntax and safety before execution.
    Input: SQL query string
    Output: validated/corrected query, or an error message
    """
    try:
        print(f"[checker] Validating: {query[:80]}...")
        # Basic validation: check for dangerous keywords
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE"]
        query_upper = query.upper().strip()
        
        if any(query_upper.startswith(kw) for kw in dangerous_keywords):
            return f"Error: Query contains forbidden operation. Only SELECT queries are allowed."
        
        if not query_upper.startswith("SELECT"):
            return f"Error: Only SELECT queries are allowed."
        
        print(f"[checker] Valid")
        return query
    except Exception as e:
        error = f"Query validation error: {str(e)}"
        print(f"[ERROR] {error}")
        traceback.print_exc()
        return error


@mcp.tool()
async def sql_db_query(query: str) -> str:
    """
    Execute a SQL SELECT query and return the results.
    Input: a valid SQL SELECT query
    Output: query results as a string
    """
    try:
        print(f"[query] Executing: {query[:80]}...")
        result = db.run(query)
        result_str = str(result)
        preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
        print(f"[query] Result preview: {preview}")
        return result_str
    except Exception as e:
        error = f"Query execution error: {str(e)}"
        print(f"[ERROR] {error}")
        traceback.print_exc()
        return error


if __name__ == "__main__":
    print(f"\nStarting IPLText2SQLServer")
    print(f"  URL      : http://localhost:{PORT}/mcp")
    print(f"  Database : {DB_PATH}")
    print(f"  Tools    : sql_db_list_tables, sql_db_schema, sql_db_query_checker, sql_db_query")
    print(f"  Status   : Running (press Ctrl+C to stop)\n")
    
    try:
        while True:
            try:
                # Run the MCP server
                # It may exit after client disconnects, so we restart it in a loop
                mcp.run(transport="streamable-http")
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n[WARNING] Server connection closed: {str(e)}")
                print("[INFO] Restarting server...\n")
                time.sleep(1)  # Brief delay before restarting
                
    except KeyboardInterrupt:
        print("\n\nServer interrupted by user. Shutting down...")
