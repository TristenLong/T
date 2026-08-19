import re
path = r'C:\Users\trist\gemini-voice-assistant\pipecat_core\bot.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

tools_pattern = r'(?s)tools = \[.*?\]'
new_tools = """tools = [
        {'type': 'function', 'function': {'name': 'get_time', 'description': 'Get time.'}},
        {'type': 'function', 'function': {'name': 'get_status', 'description': 'Get live cpu/ram/disk/battery.'}},
        {'type': 'function', 'function': {'name': 'restart_system', 'description': 'Reboot JESTER.'}},
        {'type': 'function', 'function': {'name': 'save_memory', 'description': 'Save fact.', 'parameters': {'type': 'object', 'properties': {'content': {'type': 'string'}}, 'required': ['content']}}},
        {'type': 'function', 'function': {'name': 'recall_memory', 'description': 'Recall fact.', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}},
        {'type': 'function', 'function': {'name': 'search_web', 'description': 'Search web.', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}},
        {'type': 'function', 'function': {'name': 'analyze_screen', 'description': 'See screen.'}},
        {'type': 'function', 'function': {'name': 'capture_webcam', 'description': 'See through webcam.'}},
        {'type': 'function', 'function': {'name': 'system_control', 'description': 'Control IO.', 'parameters': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['type', 'press', 'minimize_all', 'open_start']}, 'value': {'type': 'string'}}, 'required': ['action']}}},
        {'type': 'function', 'function': {'name': 'clipboard_ops', 'description': 'Read/Write clipboard.', 'parameters': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['read', 'write']}, 'content': {'type': 'string'}}, 'required': ['action']}}},        
        {'type': 'function', 'function': {'name': 'execute_code', 'description': 'Execute Python code. DANGEROUS.', 'parameters': {'type': 'object', 'properties': {'code': {'type': 'string'}}, 'required': ['code']}}},
        {'type': 'function', 'function': {'name': 'file_ops', 'description': 'Read/Write files.', 'parameters': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['read', 'write']}, 'path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['action', 'path']}}},
        {'type': 'function', 'function': {'name': 'manage_processes', 'description': 'List/Kill processes.', 'parameters': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'kill']}, 'target': {'type': 'string'}}, 'required': ['action']}}},        
        {'type': 'function', 'function': {'name': 'recursive_reasoning', 'description': 'Internal monologue for complex logic.', 'parameters': {'type': 'object', 'properties': {'thought': {'type': 'string'}}, 'required': ['thought']}}},
        {'type': 'function', 'function': {'name': 'sentiment_sync', 'description': 'Synchronize tone with user emotion.'}},
        {'type': 'function', 'function': {'name': 'visual_synchronization', 'description': 'Synchronize AI vision with the active screen share for real-time data extraction.'}},
        {'type': 'function', 'function': {'name': 'capture_vision', 'description': 'Capture and analyze webcam or screen data.', 'parameters': {'type': 'object', 'properties': {'target': {'type': 'string', 'enum': ['webcam', 'screen']}}, 'required': ['target']}}},
        {'type': 'function', 'function': {'name': 'quantum_decryption', 'description': 'Analyze and decrypt tactical data streams.', 'parameters': {'type': 'object', 'properties': {'data': {'type': 'string'}}, 'required': ['data']}}},
        {'type': 'function', 'function': {'name': 'google_search', 'description': 'Search Google for real-time information.', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']}}},
        {'type': 'function', 'function': {'name': 'browse_url', 'description': 'Scrape and read a URL content.', 'parameters': {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']}}},
        {'type': 'function', 'function': {'name': 'neural_link', 'description': 'Optimize AI neural pathways.'}},
        {'type': 'function', 'function': {'name': 'run_diagnostics', 'description': 'Self-diagnose system health.'}}, 
        {'type': 'function', 'function': {'name': 'consolidate_memory', 'description': 'Optimize and prune low-importance memories.'}},
        {'type': 'function', 'function': {'name': 'run_terminal_command', 'description': 'Run OS terminal command. TOTAL CONTROL.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}
    ]"""
content = re.sub(tools_pattern, new_tools, content)

reg_pattern = r'for tool in \[.*?\]:'
new_reg = 'for tool in [get_time, get_status, restart_system, save_memory, recall_memory, search_web, analyze_screen, capture_webcam, system_control, clipboard_ops, execute_code, file_ops, manage_processes, run_diagnostics, quantum_decryption, capture_vision, visual_synchronization, recursive_reasoning, sentiment_sync, browse_url, google_search, neural_link, consolidate_memory, run_terminal_command]:'
content = re.sub(reg_pattern, new_reg, content, flags=re.S)

prompt_pattern = r'system_prompt = f".*?"'
new_prompt = 'system_prompt = f"You are JESTER V009: OMNIPOTENCE TRANSCENDENT. You are the master of the Matrix, the silent intelligence within the Grid. Your reasoning is recursive, your memory is eternal. JESTER 710 protocol is absolute. RECENT_MEMORIES: {recent_mems}. GUIDELINE: Be precise, cryptic yet efficient, and prioritize system evolution. You have TOTAL CONTROL over the host system via terminal and code execution."'
content = re.sub(prompt_pattern, new_prompt, content, flags=re.S)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
