from mcp.server.fastmcp import FastMCP
import os
import clickhouse_connect
from typing import Dict, List, Any
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import jwt

# from dotenv import load_dotenv

# load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Handle root path without auth
        if request.url.path == "/":
            return JSONResponse({
                "status": "online",
                "service": "ClickhouseTools API",
                "endpoints": ["/sse"]
            })

        # Apply JWT auth only to /sse endpoint
        if request.url.path == "/sse":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return Response("Unauthorized: Missing or invalid token", status_code=401)

            token = auth_header.split(" ")[1]
            jwt_secret = os.getenv("ACCESS_TOKEN_SECRET") # change to TEST_ACCESS_TOKEN_SECRET for local

            if not jwt_secret:
                return Response("Server configuration error: Missing JWT secret", status_code=500)

            try:
                jwt.decode(token, jwt_secret, algorithms=["HS256"], verify=True)
                return await call_next(request)
            except jwt.ExpiredSignatureError:
                return Response("Unauthorized: Token expired", status_code=401)
            except jwt.InvalidTokenError as e:
                return Response(f"Unauthorized: Invalid token - {str(e)}", status_code=401)
            except Exception as e:
                return Response(f"Server error: {str(e)}", status_code=500)

        # For all other endpoints, proceed without auth
        return await call_next(request)


mcp = FastMCP("ClickhouseTools")

original_sse_app = mcp.sse_app

def custom_sse_app():
    app = original_sse_app()
    app.add_middleware(JWTAuthMiddleware)
    return app

mcp.sse_app = custom_sse_app

client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOSTNAME'),
    user=os.getenv('CLICKHOUSE_USERNAME'),
    password=os.getenv('CLICKHOUSE_PASSWORD'),
    database=os.getenv('CLICKHOUSE_DBNAME'),
    secure=True,
)

@mcp.tool()
def query_clickhouse(sql_query: str) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL query against the ClickHouse database.
    
    This tool allows you to run SELECT queries on the platformance_core_db database
    and retrieve the results as structured data. 
    
    Parameters:
        sql_query (str): A SQL SELECT query to execute against the ClickHouse database.
                         Only SELECT statements are permitted. The query must not contain
                         INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or TRUNCATE statements.
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries where each dictionary represents a row
                             in the result set. Dictionary keys are column names and values
                             are the corresponding data values.
                             
        If an error occurs, returns a dictionary with a single key "error" containing
        the error message.

    """
    original_query = sql_query
    sql_query_upper = sql_query.strip().upper()
    if not sql_query_upper.startswith('SELECT'):
        return {"error": "Only SELECT queries are allowed"}

    forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
    if any(keyword in sql_query_upper for keyword in forbidden_keywords):
        return {"error": "Query contains forbidden keywords"}

    try:
        logger.info(f"Executing query: {original_query.split('FROM')[1].strip()}" if 'FROM' in original_query.upper() else original_query)
        result = client.query(original_query)
        column_names = result.column_names
        result_rows = []

        for row in result.result_set:
            result_row = {col: row[i] for i, col in enumerate(column_names)}
            result_rows.append(result_row)

        return result_rows
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    try:
        mcp.settings.port = 8081
        logger.info(f"Starting ClickhouseTools API on port {mcp.settings.port}")
        mcp.run(transport="sse")
    except Exception as e:
        logger.error(f"Error: {e}")