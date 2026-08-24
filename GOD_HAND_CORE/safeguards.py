import logging
import os
import re

logger = logging.getLogger('SAFEGUARDS')

BLOCKED_PATHS = [
    r'C:\Windows',
    r'C:\Program Files',
    r'C:\Program Files (x86)',
]

BLOCKED_COMMANDS = [
    'rm -rf',
    'format c:',
    'del /s /q c:',
    'shutdown',
    'wmic product call uninstall',
    'net user',
    'passwd',
]

def is_safe_path(path):
    path = os.path.abspath(path)
    for block in BLOCKED_PATHS:
        if block.lower() in path.lower():
            return False
    return True

def is_safe_command(cmd):
    for block in BLOCKED_COMMANDS:
        if block in cmd.lower():
            return False
    return True

def validate_tool_use(tool_name, args):
    # Environment gatekeeping
    if tool_name in ['system_control', 'execute_code', 'run_terminal_command']:
        allow_flag = os.getenv('JESTER_ALLOW_DANGEROUS_TOOLS', 'false').lower() == 'true'
        if not allow_flag:
            return False, 'ACCESS_DENIED: DANGEROUS_TOOLS_DISABLED_BY_ENV'

    # Path validation
    if 'path' in args:
        if not is_safe_path(args['path']):
            return False, 'ACCESS_DENIED: PROTECTED_SYSTEM_PATH'

    # Command validation
    cmd_str = str(args.get('command', '')) + str(args.get('code', ''))
    if cmd_str and not is_safe_command(cmd_str):
        return False, 'ACCESS_DENIED: DANGEROUS_COMMAND_DETECTED'

    # Confirmation token (Simple check for 'CONFIRM_TOKEN' in args)
    if tool_name in ['system_control', 'run_terminal_command', 'execute_code']:
        token = args.get('confirmation_token')
        expected = os.getenv('JESTER_CONFIRMATION_TOKEN')
        if expected and token != expected:
            return False, 'ACCESS_DENIED: INVALID_CONFIRMATION_TOKEN'

    return True, 'SAFE'
