import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# `command`/`args` reach these helpers from request bodies (/api/execute_tool's
# mcp_execute branch), so the spawned process is caller-controlled. Handing it a
# full os.environ.copy() also handed it every API key the server holds. Pass the
# variables an MCP server legitimately needs and nothing else.
_ENV_ALLOWLIST = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "TMPDIR", "HOME", "HOMEDRIVE", "HOMEPATH", "USERPROFILE",
    "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA",
    "LANG", "LC_ALL", "TZ", "NODE_PATH", "NPM_CONFIG_PREFIX",
)


def _mcp_env():
    """Minimal environment for a spawned MCP server, without our secrets."""
    env = {k: v for k, v in os.environ.items() if k.upper() in _ENV_ALLOWLIST}
    # Anything explicitly namespaced for MCP servers is opt-in by the operator.
    env.update({k: v for k, v in os.environ.items() if k.startswith("MCP_")})
    return env


def _spawn_command(command: str, args: list) -> list:
    """Return a spawnable argv, routing bare .cmd/.ps1 shims through cmd.exe on
    Windows so `npx`-style commands are not a FileNotFoundError / bad win32 exe."""
    if os.name != 'nt':
        return [command] + args
    bare = os.path.basename(command)
    is_absolute_exe = os.path.isabs(command) and command.lower().endswith(('.exe', '.bat', '.cmd', '.ps1'))
    if not is_absolute_exe and (bare == 'npx' or bare == 'npm' or not os.path.splitext(bare)[1]):
        return ['cmd.exe', '/c', command] + args
    return [command] + args


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
    argv = _spawn_command(command, args)
    server_params = StdioServerParameters(
        command=argv[0],
        args=argv[1:],
        env=_mcp_env()
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
                
                # Format result (older SDKs used isError, new ones is_error)
                is_err = getattr(result, 'is_error', None)
                if is_err is None:
                    is_err = getattr(result, 'isError', False)
                if is_err:
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
    argv = _spawn_command(command, args)
    server_params = StdioServerParameters(command=argv[0], args=argv[1:], env=_mcp_env())
    
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
