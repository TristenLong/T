import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def run_mcp_tool(command: str, args: list, tool_name: str, tool_args: dict) -> str:
    """
    Synchronous wrapper to launch an MCP server, connect via stdio, execute a single tool, and return the result.
    Example: 
      command="npx", 
      args=["-y", "@modelcontextprotocol/server-filesystem", "C:\\"], 
      tool_name="list_directory",
      tool_args={"path": "C:\\"}
    """
    try:
        return asyncio.run(_async_run_mcp_tool(command, args, tool_name, tool_args))
    except Exception as e:
        return f"MCP_ERROR: {str(e)}"

async def _async_run_mcp_tool(command: str, args: list, tool_name: str, tool_args: dict) -> str:
    # Use current env but add PATH if needed
    env = os.environ.copy()
    
    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env
    )
    
    output_log = []
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Check if tool exists
                tools = await session.list_tools()
                tool_exists = any(t.name == tool_name for t in tools.tools)
                if not tool_exists:
                    available = [t.name for t in tools.tools]
                    return f"MCP_ERROR: Tool '{tool_name}' not found on server. Available tools: {available}"
                
                # Execute tool
                result = await session.call_tool(tool_name, arguments=tool_args)
                
                # Format result
                if result.isError:
                    return f"MCP_TOOL_ERROR: {result.content}"
                
                # Return text content
                return "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                
    except Exception as e:
        return f"MCP_CLIENT_ERROR: {str(e)}"

def list_mcp_tools(command: str, args: list) -> str:
    """
    Helper to list available tools on a given MCP server.
    """
    try:
        return asyncio.run(_async_list_mcp_tools(command, args))
    except Exception as e:
        return f"MCP_ERROR: {str(e)}"

async def _async_list_mcp_tools(command: str, args: list) -> str:
    env = os.environ.copy()
    server_params = StdioServerParameters(command=command, args=args, env=env)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                
                tool_list = []
                for t in tools.tools:
                    schema = t.inputSchema if hasattr(t, 'inputSchema') else {}
                    tool_list.append(f"- {t.name}: {t.description}\n  Schema: {json.dumps(schema)}")
                
                return "\n".join(tool_list)
    except Exception as e:
        return f"MCP_CLIENT_ERROR: {str(e)}"
