import os
import json
import interpreter_core
import research_core
import system_core
import ingest_core
import vector_core
from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def execute_mission(objective):
    if not OPENAI_API_KEY: return "NO_BRAIN_AVAILABLE"
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    history = []
    MAX_STEPS = 5
    
    report = f"MISSION: {objective}\n"

    for i in range(MAX_STEPS):
        # 1. Decide Next Action
        prompt = f"""
        OBJECTIVE: {objective}
        HISTORY: {json.dumps(history[-3:], indent=2)}
        
        Available Tools:
        - RESEARCH: args(query) -> Web Search
        - CODE: args(code) -> Run Python
        - READ_FILE: args(path) -> Read local file
        - SYSTEM: args(command) -> Run shell command
        - FINISH: args(summary) -> End mission
        
        Return JSON: {{ "tool": "TOOL_NAME", "args": {{...}}, "thought": "Why?" }}
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            decision = json.loads(response.choices[0].message.content)
            
            tool = decision.get("tool")
            args = decision.get("args")
            thought = decision.get("thought")
            
            report += f"\n[STEP {i+1}] THOUGHT: {thought}\nACTION: {tool} {args}\n"
            
            result = "UNKNOWN"
            
            if tool == "FINISH":
                report += f"CONCLUSION: {args.get('summary')}"
                break
                
            elif tool == "RESEARCH":
                result = research_core.deep_research(args.get("query"))
            elif tool == "CODE":
                result = interpreter_core.run(args.get("code"))
            elif tool == "READ_FILE":
                path = args.get("path")
                if os.path.exists(path):
                    with open(path, "r") as f: result = f.read()[:2000]
                else: result = "FILE_NOT_FOUND"
            elif tool == "SYSTEM":
                # Dangerous, strict control in real deployment
                result = "SYSTEM_CMD_SIMULATED (Safety Protocol)" 
                
            history.append({"step": i, "tool": tool, "result": str(result)[:500]}) # Truncate history
            report += f"RESULT: {str(result)[:200]}...\n"
            
        except Exception as e:
            report += f"ERROR: {e}\n"
            break
            
    return report
