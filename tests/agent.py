import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import weave
import time
import jwt  
# Load environment variables
load_dotenv()

weave.init(os.getenv('WEAVE_PROJECT'))

# Function to run the agent with MCP tools
@weave.op()
async def run_agent():
    # Initialize model
    model = ChatOpenAI(model="gpt-4o")
    jwt_secret = os.getenv("TEST_ACCESS_TOKEN_SECRET")
    if not jwt_secret:
        raise ValueError("TEST_ACCESS_TOKEN_SECRET environment variable not set")

    # Create a more secure token with required fields
    payload = {
        "sub": "agent", 
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "iss": "clickhouse_mcp_client"
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    # Add JWT auth header
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    headers = {"Authorization": f"Bearer {token}"}
    # Connect to MCP server
    MCP_URL = os.getenv("MCP_SERVER_URL")
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Get tools
            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {[tool.name for tool in tools]}")
            
            # Create the agent with ReAct
            agent = create_react_agent(model, tools)
            
            # Example 3: Run a custom query
            print("\n--- Example 3: Custom query ---")
            response = await agent.ainvoke({
                "messages": "Run a query to get the top 5 rows from one of the tables - actualized_volumes and give a summary"
            })
            print("Agent response:", response)


if __name__ == "__main__":
    asyncio.run(run_agent())