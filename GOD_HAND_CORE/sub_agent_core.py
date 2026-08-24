import logging
import threading
import time
import uuid

from duckduckgo_search import DDGS

import memory_core
from llm_router import generate_completion

logger = logging.getLogger("SUB_AGENT_CORE")
logger.setLevel(logging.INFO)

active_agents = {}

def spawn_agent(task_description: str, agent_type: str = "researcher") -> str:
    """Spawns a background AI agent to complete a task autonomously."""
    agent_id = str(uuid.uuid4())[:8]
    
    def agent_worker(a_id, desc, type_name):
        logger.info(f"Agent [{a_id}] ({type_name}) started task: {desc}")
        active_agents[a_id] = {"status": "RUNNING", "task": desc, "type": type_name}
        
        try:
            # Simple researcher sub-agent logic
            if type_name == "researcher":
                with DDGS() as ddgs:
                    results = [r for r in ddgs.text(desc, max_results=3)]
                
                # True LLM synthesis of the research using the router (Ollama -> OpenAI)
                raw_text = " | ".join([r.get('body', '') for r in results])
                
                summary = generate_completion(
                    messages=[{"role": "user", "content": f"Synthesize this research for task: {desc}\n\nData: {raw_text}"}],
                    require_json=False
                )
                
                # Drop findings into Jester's Long Term Memory so Jester naturally remembers it later
                memory_core.save(f"Sub-Agent {a_id} finished task '{desc}'. Findings: {summary}", importance=7)
                
                active_agents[a_id]["status"] = "COMPLETED"
                active_agents[a_id]["result"] = summary
                logger.info(f"Agent [{a_id}] completed task.")
            elif type_name == "mcp_agent":
                import mcp_client_core
                import json
                messages = [
                    {"role": "system", "content": "You are a background MCP Agent. You can execute MCP tools by returning ONLY valid JSON in this format: {\"tool\": \"mcp\", \"cmd\": \"npx\", \"args\": [\"-y\", \"@modelcontextprotocol/server-filesystem\", \"C:\\\\\"], \"mcp_tool\": \"list_directory\", \"mcp_args\": {\"path\": \"C:\\\\\"}}. If you are finished, return plain text."},
                    {"role": "user", "content": desc}
                ]
                
                final_result = ""
                for step in range(5):
                    reply = generate_completion(messages, require_json=False)
                    try:
                        data = json.loads(reply)
                        if data.get("tool") == "mcp":
                            tool_res = mcp_client_core.run_mcp_tool(
                                data.get("cmd", "npx"),
                                data.get("args", []),
                                data.get("mcp_tool"),
                                data.get("mcp_args", {})
                            )
                            messages.append({"role": "assistant", "content": reply})
                            messages.append({"role": "user", "content": f"Tool Result:\n{tool_res}"})
                        else:
                            final_result = reply
                            break
                    except json.JSONDecodeError:
                        final_result = reply
                        break
                        
                memory_core.save(f"Sub-Agent {a_id} ({type_name}) finished task '{desc}'. Result: {final_result}", importance=6)
                active_agents[a_id]["status"] = "COMPLETED"
                active_agents[a_id]["result"] = final_result
            else:
                # Real LLM Sub-Agent Spawning via Router
                result = generate_completion(
                    messages=[{"role": "user", "content": f"You are a highly capable AI Sub-Agent ({type_name}). Complete this specific sub-task for JESTER: {desc}\nRespond clearly and concisely with the result."}],
                    require_json=False
                )
                
                memory_core.save(f"Sub-Agent {a_id} ({type_name}) finished task '{desc}'. Result: {result}", importance=5)
                active_agents[a_id]["status"] = "COMPLETED"
                active_agents[a_id]["result"] = result
        except Exception as e:
            active_agents[a_id]["status"] = f"FAILED: {str(e)}"
            logger.error(f"Agent [{a_id}] failed: {e}")

    thread = threading.Thread(target=agent_worker, args=(agent_id, task_description, agent_type), daemon=True)
    thread.start()
    
    return f"Sub-Agent {agent_id} ({agent_type}) spawned successfully and is running in the background."

def list_active_agents() -> dict:
    """Returns the status of all spawned sub-agents."""
    return active_agents
