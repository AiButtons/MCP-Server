import asyncio
import os
import json
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

# Initialize Weave if environment variable is set
weave.init(os.getenv('WEAVE_PROJECT'))

@weave.op()
async def get_all_schemas():
    # Initialize model
    model = ChatOpenAI(model="gpt-4o")
    jwt_secret = os.getenv("TEST_ACCESS_TOKEN_SECRET")
    if not jwt_secret:
        raise ValueError("TEST_ACCESS_TOKEN_SECRET environment variable not set")

    # Create a more secure token with required fields
    payload = {
        "sub": "schema_extractor", 
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "iss": "clickhouse_schema_extractor"
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    # Add JWT auth header
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    headers = {"Authorization": f"Bearer {token}"}
    
    # Connect to MCP server
    async with sse_client("http://localhost:8081/sse", headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Get tools
            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {[tool.name for tool in tools]}")
            
            # Create the agent with ReAct
            agent = create_react_agent(model, tools)
            
            # Step 1: Get list of all tables
            print("\n--- Getting all tables ---")
            tables_response = await agent.ainvoke({
                "messages": [{
                    "role": "user", 
                    "content": "List all tables in the database. Return only the table names in a clean list format."
                }]
            })
            print("Tables response received")
            
            # Extract table names from the response
            tables_message = tables_response["messages"][-1].content
            
            # Process the list to extract table names
            # This handles the case where the LLM formats the response as a numbered list
            table_names = []
            for line in tables_message.strip().split('\n'):
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Remove numbering and extra characters
                cleaned_line = line.strip()
                if "." in cleaned_line:
                    # Handle numbered lists (1. table_name)
                    parts = cleaned_line.split('.', 1)
                    if len(parts) > 1 and parts[0].strip().isdigit():
                        cleaned_line = parts[1].strip()
                
                table_names.append(cleaned_line)
            
            # Schema info structure
            schema_info = {
                "tables": {}
            }
            
            # Step 2: Get schema for each table one by one
            print(f"\n--- Getting schema for {len(table_names)} tables ---")
            for i, table_name in enumerate(table_names):
                print(f"Processing table {i+1}/{len(table_names)}: {table_name}")
                
                # Skip tables with special characters if they cause issues
                if any(c in table_name for c in ['`', '"', "'"]):
                    print(f"Skipping table with special characters: {table_name}")
                    continue
                
                try:
                    # Get schema for each table
                    schema_response = await agent.ainvoke({
                        "messages": [{
                            "role": "user", 
                            "content": f"Describe the structure of the table '{table_name}'. Return only the column details."
                        }]
                    })
                    
                    # Extract schema information
                    schema_message = schema_response["messages"][-1].content
                    schema_info["tables"][table_name] = {
                        "raw_description": schema_message,
                        "columns": parse_schema_description(schema_message)
                    }
                except Exception as e:
                    print(f"Error getting schema for {table_name}: {e}")
                    schema_info["tables"][table_name] = {
                        "error": str(e)
                    }
            
            # Save schema info to file
            output_file = "clickhouse_schema.json"
            with open(output_file, "w") as f:
                json.dump(schema_info, f, indent=2)
            
            print(f"Schema information saved to {output_file}")
            
            return schema_info

def parse_schema_description(description):
    """Parse the schema description from the LLM response"""
    columns = []
    lines = description.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        # Skip empty lines and non-column descriptions
        if not line or ":" not in line:
            continue
            
        # Handle both bullet points and dash formats
        if line.startswith('-') or line.startswith('*'):
            line = line[1:].strip()
            
        # Extract name and type from formats like:
        # - `column_name`: Type
        # - column_name: Type
        # - column_name (Type)
        if ':' in line:
            parts = line.split(':', 1)
            name_part = parts[0].strip()
            type_part = parts[1].strip() if len(parts) > 1 else "Unknown"
            
            # Clean up name part (remove backticks, etc.)
            name = name_part.strip('`').strip()
            
            columns.append({
                "name": name,
                "type": type_part
            })
    
    return columns

@weave.op()
async def run_agent():
    """Original agent function for comparison"""
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
    async with sse_client("http://localhost:8081/sse", headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Get tools
            tools = await load_mcp_tools(session)
            print(f"Loaded {len(tools)} tools: {[tool.name for tool in tools]}")
            
            # Create the agent with ReAct
            agent = create_react_agent(model, tools)
            
            # Example 1: List tables
            print("\n--- Example 1: List tables ---")
            response = await agent.ainvoke({
                "messages": "List all tables in the database"
            })
            print("Agent response:", response)
            
            # Example 2: Describe a table structure
            print("\n--- Example 2: Describe a table ---")
            response = await agent.ainvoke({
                "messages": "Show me the structure of one of the tables"
            })
            print("Agent response:", response)
            
            # Example 3: Run a custom query
            print("\n--- Example 3: Custom query ---")
            response = await agent.ainvoke({
                "messages": "Run a query to get the top 5 rows from one of the tables"
            })
            print("Agent response:", response)

async def main():
    """Main function to run the appropriate operation"""
    # Choose which operation to run
    operation = os.getenv("OPERATION", "get_schemas").lower()
    
    if operation == "examples":
        print("Running examples with agent...")
        await run_agent()
    else:
        print("Extracting schema for all tables...")
        await get_all_schemas()

if __name__ == "__main__":
    asyncio.run(main())