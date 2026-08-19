import os
path = r'C:\Users\trist\gemini-voice-assistant\pipecat_core\bot.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'run_diagnostics' in line and 'consolidate_memory' in line:
        new_lines.append(\"        {'type': 'function', 'function': {'name': 'run_diagnostics', 'description': 'Self-diagnose system health.'}},\\n\")
        new_lines.append(\"        {'type': 'function', 'function': {'name': 'consolidate_memory', 'description': 'Optimize and prune low-importance memories.'}},\\n\")
        skip = True
        continue
    if skip and 'run_terminal_command' in line:
        new_lines.append(\"        {'type': 'function', 'function': {'name': 'run_terminal_command', 'description': 'Run OS terminal command. TOTAL CONTROL.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}\\n\")
        skip = False
        continue
    if skip and i > 0 and ']' in line and '[' not in line: # Found the end of tools list
        new_lines.append(\"    ]\\n\")
        skip = False
        continue
    if not skip or ('run_terminal_command' not in line and ']' not in line):
        if \"'required': ['command']}}}\" in line and 'run_terminal_command' not in line:
            continue
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
