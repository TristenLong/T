import asyncio
import base64
import datetime
import io
import json
import os
import subprocess
import sys
import time
import traceback
import warnings

import cv2
import numpy as np
import psutil
import pyautogui
import pyperclip
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from google import genai
from loguru import logger
from PIL import Image

import browser_core
import coder_core
import computer_use
import constructor_core
import diagnostics_suite
import dream_core
import evolution_core
import genesis_core
import goal_core
import ingest_core
import interpreter_core
import learning_core
import memory_core
import mcp_client_core
import mutation_core
import observer_core
import offline_brain
import reddit_core
import research_core
import safeguards
import strategy_core
import synapse_core
import system_core
import vector_core

warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

logger.add('bot_debug.log', rotation='1 MB', level='DEBUG')

print('?? Starting JESTER V2000: SINGULARITY (SWARM EDITION)...')

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
CARTESIA_API_KEY = os.getenv('CARTESIA_API_KEY')
FREE_TIER_MODE = os.getenv('FREE_TIER_MODE', 'false').lower() == 'true'
PRIMARY_MODEL = os.getenv('JESTER_PRIMARY_LLM', os.getenv('JESTER_GEMINI_MODEL', 'gemini-3.1-pro'))
OPENAI_MODEL = os.getenv('JESTER_OPENAI_MODEL', 'gpt-4o')
ENABLE_GEMINI_TOOL = os.getenv('JESTER_ENABLE_GEMINI_TOOL', 'false').lower() == 'true'

# Initialize services safely
DeepgramSTTService = None
CartesiaTTSService = None

# LLM Configuration with FREE Tier Override
if FREE_TIER_MODE:
    logger.info("?? FREE TIIER MODE ACTIVE - Using free models (OpenRouter meta-llama/Meta-Llama-3-8B-Instruct-Free:free)")
    # In free tier mode, we use the primary LLM which is set to a free model
    LLM_API_KEY = GEMINI_API_KEY if GEMINI_API_KEY else None
else:
    LLM_API_KEY = OPENAI_API_KEY if OPENAI_API_KEY else (GEMINI_API_KEY if GEMINI_API_KEY else None)

# Determine if we can run at all
if not OPENAI_API_KEY and not GEMINI_API_KEY and not FREE_TIER_MODE:
    logger.error('No OPENAI_API_KEY or GEMINI_API_KEY found in env. JESTER cannot run without a primary LLM.')
    sys.exit(1)

# Audio Provider Detection
if DEEPGRAM_API_KEY and CARTESIA_API_KEY:
    try:
        from pipecat.services.cartesia.tts import CartesiaTTSService as CartTTS
        from pipecat.services.deepgram.stt import DeepgramSTTService as DGSTT
        DeepgramSTTService = DGSTT
        CartesiaTTSService = CartTTS
        AUDIO_PROVIDER = 'deepgram_cartesia'
    except Exception:
        AUDIO_PROVIDER = None
elif OPENAI_API_KEY:
    AUDIO_PROVIDER = 'openai'
else:
    AUDIO_PROVIDER = None

TEXT_ONLY_MODE = os.getenv('TEXT_ONLY_MODE', 'false').lower() == 'true' or AUDIO_PROVIDER is None
if TEXT_ONLY_MODE:
    logger.warning('?? Running in TEXT-ONLY MODE (no audio services available)')
else:
    logger.info(f'?? Audio provider selected: {AUDIO_PROVIDER}')

async def analyze_image(prompt, pil_image):
    try:
        if GEMINI_API_KEY:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(model='gemini-1.5-flash', contents=[prompt, pil_image])
            return response.text
        return 'Vision Error: No GEMINI_API_KEY available.'
    except Exception as e:
        return f'Vision Error: {str(e)}'

# Pipecat imports
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService as RealCartesiaTTS
from pipecat.services.deepgram.stt import DeepgramSTTService as RealDeepgramSTT
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.transports.base_transport import BaseTransport, TransportParams

# VAD and Turn Analyzer setup safely
SileroVADAnalyzer = None
LocalSmartTurnAnalyzerV3 = None

try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer as SVAD
    SileroVADAnalyzer = SVAD
except Exception as e:
    logger.warning(f'?? SileroVADAnalyzer unavailable: {e}')

try:
    from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
except Exception as e:
    logger.warning(f'?? LocalSmartTurnAnalyzerV3 unavailable: {e}')

# Utility Functions
import requests

try:
    import jester_auth
except ImportError:  # bot.py can be launched with a different sys.path
    jester_auth = None


def notify_frontend(event_type, message, payload=None):
    try:
        # /api/internal/bot_event now requires the shared token; without it the
        # server returns 401 and every bot event is silently dropped.
        headers = jester_auth.auth_headers() if jester_auth else {}
        requests.post('http://127.0.0.1:5000/api/internal/bot_event', json={
            'event_type': event_type,
            'message': message,
            'payload': payload or {}
        }, headers=headers, timeout=2)
    except Exception:
        pass

async def get_time(f,t,a,l,c,r): await r({'time': datetime.datetime.now().strftime('%I:%M %p')})
async def get_status(f,t,a,l,c,r): await r({'cpu': f'{psutil.cpu_percent()}%', 'ram': f'{psutil.virtual_memory().percent}%', 'status': 'SWARM_ONLINE'})
async def restart_system(f,t,a,l,c,r): await r({'status': 'REBOOTING'}); sys.exit(0)
async def save_memory(f,t,a,l,c,r): c=a.get('content'); memory_core.save(c, a.get('importance', 3)); vector_core.save_semantic(c); await r({'result': 'SAVED_DUAL_CORE'})
async def recall_memory(f,t,a,l,c,r): await r({'memories': memory_core.retrieve(a.get('query'))})
async def consolidate_memory(f,t,a,l,c,r): await r({'result': memory_core.consolidate()})
async def recall_semantic(f,t,a,l,c,r):
    res = vector_core.search_semantic(a.get('query'))
    await r({'memories': str(res)})

async def run_interactive_code(f,t,a,l,c,r):
    code = a.get('code')
    res = interpreter_core.run(code)
    await r(res)

async def dispatch_coder_swarm(f,t,a,l,c,r):
    prompt = a.get('prompt')
    notify_frontend('ui_alert', f"Architect CoderCore Dispatched: {prompt}")
    coder = coder_core.CoderCore(memory_core)
    res = await coder.run_coding_task(prompt)
    await r({'coder_response': res})

async def dispatch_browser_swarm(f,t,a,l,c,r):
    task = a.get('task')
    notify_frontend('ui_alert', f"Navigator BrowserCore Dispatched: {task}")
    browser = browser_core.BrowserCore(memory_core)
    res = await browser.navigate_and_interact(task)
    await r({'browser_response': res})

async def execute_computer_use(f,t,a,l,c,r):
    action = a.get('action')
    params = a.get('params', {})
    notify_frontend('ui_alert', f"Computer Use Activated: {action}")
    res = computer_use.execute_computer_action(action, params)
    await r({'computer_action_result': res})

async def conduct_deep_research(f,t,a,l,c,r):
    await r({"status": "RESEARCHING", "message": "Deploying web spiders..."})
    notify_frontend('ui_alert', f"Deep Research Initialized: {a.get('query')}")
    res = research_core.deep_research(a.get("query"))
    await r({"research_data": res})

async def construct_dashboard(f,t,a,l,c,r):
    res = constructor_core.create_dashboard(a.get("filename"), a.get("content"))
    await r({"status": "CONSTRUCTED", "url": res})

async def scan_network(f,t,a,l,c,r):
    res = constructor_core.scan_network()
    await r({"network_map": res})

async def memorize_fact(f,t,a,l,c,r):
    res = learning_core.add_fact(a.get("subject"), a.get("predicate"), a.get("object"))
    await r({"status": res})

async def query_knowledge(f,t,a,l,c,r):
    res = learning_core.query_graph(a.get("query"))
    await r({"knowledge": res})

async def watch_and_learn(f,t,a,l,c,r):
    await r({"status": "OBSERVING", "message": "Analyzing visual input..."})
    res = observer_core.analyze_and_extract()
    await r(res)

async def dream_visual(f,t,a,l,c,r):
    await r({"status": "DREAMING", "message": "Visualizing concept..."})
    res = dream_core.generate_dream(a.get("prompt"))
    await r(res)

async def optimize_system(f,t,a,l,c,r):
    target = a.get("target", "mining")
    await r({"status": "OPTIMIZING", "mode": target})
    res = system_core.optimize(target)
    await r({"report": res})

async def set_system_directive(f,t,a,l,c,r):
    res = goal_core.set_directive(a.get("goal"))
    await r({"status": res})

async def create_new_tool(f,t,a,l,c,r):
    name = a.get("name")
    code = a.get("python_code")
    res = genesis_core.create_tool(name, code)
    await r({"status": res})
    if "GENESIS_COMPLETE" in res:
        import sys
        sys.exit(0)  # Restart to load

async def ingest_files(f,t,a,l,c,r):
    path = a.get("path")
    await r({"status": "ARCHIVING", "message": f"Scanning {path}..."})
    res = ingest_core.ingest_directory(path)
    await r({"report": res})

async def switch_to_offline(f,t,a,l,c,r):
    msg = a.get("message", "status")
    res = offline_brain.brain.chat(msg)
    await r({"offline_response": res})

async def mastermind_solve(f,t,a,l,c,r):
    obj = a.get("objective")
    await r({"status": "STRATEGIZING", "message": f"Planning: {obj}"})
    res = strategy_core.execute_mission(obj)
    await r({"mission_report": res})

async def mutate_code(f,t,a,l,c,r):
    res = mutation_core.mutate_function(a.get("filename"), a.get("function_name"), a.get("instruction"))
    await r({"status": res})
    if "MUTATED" in res:
        import sys
        sys.exit(0)

async def search_web(f,t,a,l,c,r):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(a.get('query'), max_results=5))
            res = [{'title': r.get('title'), 'snippet': r.get('body'), 'url': r.get('href')} for r in results]
            await r({'results': res})
    except Exception as e:
        await r({'error': str(e)})

async def analyze_screen(f,t,a,l,c,r):
    try:
        desc = await analyze_image('Describe this screen in detail for the Architect.', pyautogui.screenshot())
        await r({'description': desc})
    except Exception as e:
        await r({'error': str(e)})

async def capture_webcam(f,t,a,l,c,r):
    try:
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if ret:
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            desc = await analyze_image('Describe what you see in this webcam image.', img)
            await r({'description': desc})
        else:
            await r({'error': 'WEBCAM_OFFLINE'})
    except Exception as e:
        await r({'error': str(e)})

async def system_control(f,t,a,l,c,r):
    safe, msg = safeguards.validate_tool_use('system_control', a)
    if not safe:
        await r({'error': msg})
        return
    act, val = a.get('action'), a.get('value')
    if act == 'type':
        pyautogui.write(val)
    elif act == 'press':
        pyautogui.press(val)
    elif act == 'minimize_all':
        pyautogui.hotkey('win', 'd')
    elif act == 'open_start':
        pyautogui.press('win')
    await r({'status': 'DONE'})

async def execute_code(f,t,a,l,c,r):
    safe, msg = safeguards.validate_tool_use('execute_code', a)
    if not safe:
        await r({'error': msg})
        return
    try:
        p = subprocess.Popen([sys.executable, '-c', a.get('code')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        o, e = p.communicate(timeout=10)
        await r({'stdout': o, 'stderr': e})
    except Exception as e:
        await r({'error': str(e)})

async def run_terminal_command(f,t,a,l,c,r):
    safe, msg = safeguards.validate_tool_use('run_terminal_command', a)
    if not safe:
        await r({'error': msg})
        return
    try:
        p = subprocess.run(a.get('command'), shell=True, capture_output=True, text=True, timeout=10)
        await r({'stdout': p.stdout, 'stderr': p.stderr})
    except Exception as e:
        await r({'error': str(e)})

async def run_diagnostics(f,t,a,l,c,r):
    try:
        report = diagnostics_suite.get_system_report()
        await r({'status': 'COMPLETE', 'report': report})
    except Exception as e:
        await r({'error': str(e)})

async def check_reddit(f,t,a,l,c,r):
    sub = a.get('subreddit')
    if not sub:
        await r({'error': 'SUBREDDIT_MISSING'})
    else:
        data = reddit_core.scan_subreddit(sub)
        await r({'reddit_data': data})

async def browse_url(f,t,a,l,c,r):
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(a.get('url'), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        await r({'content': soup.get_text()[:2000]})
    except Exception as e:
        await r({'error': str(e)})

async def clipboard_ops(f,t,a,l,c,r):
    act, val = a.get('action'), a.get('content', '')
    if act == 'read':
        await r({'clipboard': pyperclip.paste()})
    elif act == 'write':
        pyperclip.copy(val)
        await r({'status': 'COPIED'})

async def file_ops(f,t,a,l,c,r):
    safe, msg = safeguards.validate_tool_use('file_ops', a)
    if not safe:
        await r({'error': msg})
        return
    act, path, content = a.get('action'), a.get('path'), a.get('content', '')
    try:
        if act == 'read':
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as file:
                    await r({'content': file.read()[:2000]})
            else:
                await r({'error': 'FILE_NOT_FOUND'})
        elif act == 'write':
            with open(path, 'w', encoding='utf-8') as file:
                file.write(content)
            await r({'status': 'WRITTEN'})
    except Exception as e:
        await r({'error': str(e)})

async def manage_processes(f,t,a,l,c,r):
    act, target = a.get('action'), a.get('target', '')
    try:
        if act == 'list':
            procs = [(p.pid, p.name()) for p in psutil.process_iter(['name'])][:30]
            await r({'processes': str(procs)})
        elif act == 'kill':
            for p in psutil.process_iter(['name']):
                if target.lower() in p.name().lower():
                    p.kill()
                    await r({'status': f'KILLED {p.name()}'})
                    return
            await r({'status': 'PROCESS_NOT_FOUND'})
    except Exception as e:
        await r({'error': str(e)})

async def capture_vision(f,t,a,l,c,r):
    target = a.get('target', 'webcam')
    if target == 'screen':
        await analyze_screen(f,t,a,l,c,r)
    else:
        await capture_webcam(f,t,a,l,c,r)

async def ask_gemini(f,t,a,l,c,r):
    try:
        if not GEMINI_API_KEY:
            await r({'error': 'GEMINI_KEY_MISSING'})
        else:
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(model=PRIMARY_MODEL, contents=a.get('query'))
            await r({'gemini_response': resp.text})
    except Exception as e:
        await r({'error': str(e)})

async def solve_offline(f,t,a,l,c,r):
    problem = a.get('problem')
    tools = {
        'run_cmd': lambda x: subprocess.run(x, shell=True, capture_output=True, text=True).stdout,
        'read_file': lambda x: open(x, 'r').read() if os.path.exists(x) else 'Not Found',
        'list_dir': lambda x: str(os.listdir(x)) if os.path.exists(x) else 'Not Found'
    }

    if not offline_brain.brain.is_ready:
        offline_brain.brain.initialize()

    res = offline_brain.brain.solve(problem, tools)
    await r({'solution': res})

async def mcp_execute(f,t,a,l,c,r):
    mcp_cmd = a.get('command', 'npx')
    mcp_args = a.get('args', [])
    mcp_tool = a.get('tool_name')
    mcp_tool_args = a.get('tool_args', {})
    if not mcp_tool:
        await r({'error': 'tool_name is required'})
        return
    res = mcp_client_core.run_mcp_tool(mcp_cmd, mcp_args, mcp_tool, mcp_tool_args)
    await r({'mcp_response': res})

async def run_bot(transport, runner_args):
    try:
        stt = None
        tts = None

        if not TEXT_ONLY_MODE and AUDIO_PROVIDER:
            if AUDIO_PROVIDER == 'deepgram_cartesia' and DeepgramSTTService and CartesiaTTSService:
                stt = DeepgramSTTService(api_key=DEEPGRAM_API_KEY or "", model='nova-3', smart_format=True)
                tts = CartesiaTTSService(api_key=CARTESIA_API_KEY or "", voice_id='71a7ad14-091c-4e8e-a314-022ece01c121')
            elif AUDIO_PROVIDER == 'openai' and OPENAI_API_KEY:
                stt = OpenAISTTService(api_key=OPENAI_API_KEY, model='whisper-1')
                tts = OpenAITTSService(api_key=OPENAI_API_KEY, voice='onyx', model='tts-1')

        tools = [
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
            {'type': 'function', 'function': {'name': 'capture_vision', 'description': 'Capture and analyze webcam or screen data.', 'parameters': {'type': 'object', 'properties': {'target': {'type': 'string', 'enum': ['webcam', 'screen']}}, 'required': ['target']}}},
            {'type': 'function', 'function': {'name': 'browse_url', 'description': 'Scrape and read a URL content.', 'parameters': {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']}}},
            {'type': 'function', 'function': {'name': 'run_diagnostics', 'description': 'Self-diagnose system health.'}},
            {'type': 'function', 'function': {'name': 'consolidate_memory', 'description': 'Optimize and prune low-importance memories.'}},
            {'type': 'function', 'function': {'name': 'run_terminal_command', 'description': 'Run OS terminal command. TOTAL CONTROL.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}},
            {'type': 'function', 'function': {'name': 'dispatch_coder_swarm', 'description': 'Dispatch autonomous coding task to Architect CoderCore sub-agent.', 'parameters': {'type': 'object', 'properties': {'prompt': {'type': 'string'}}, 'required': ['prompt']}}},
            {'type': 'function', 'function': {'name': 'dispatch_browser_swarm', 'description': 'Dispatch web navigation task to Navigator BrowserCore sub-agent.', 'parameters': {'type': 'object', 'properties': {'task': {'type': 'string'}}, 'required': ['task']}}},
            {'type': 'function', 'function': {'name': 'execute_computer_use', 'description': 'Direct mouse and keyboard control via Computer Use API.', 'parameters': {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['info', 'move', 'click', 'type', 'press', 'hotkey', 'screenshot']}, 'params': {'type': 'object', 'description': 'Dictionary of args (e.g., {"x": 100, "y": 200, "text": "hello", "key": "enter", "keys": ["ctrl", "c"]})'}}, 'required': ['action']}}},
            {'type': 'function', 'function': {'name': 'mcp_execute', 'description': 'Execute an MCP tool command.', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}, 'tool_name': {'type': 'string'}, 'tool_args': {'type': 'object'}}, 'required': ['tool_name']}}}
        ]

        # LLM Selection with FREE_TIER_MODE override
        if FREE_TIER_MODE:
            # In free tier mode, we use a free model without requiring another API key
            # The free model runs on OpenRouter's infrastructure
            llm = GoogleLLMService(api_key=GEMINI_API_KEY or "", model=PRIMARY_MODEL)
            logger.info(f"?? LLM initialized with FREE model: {PRIMARY_MODEL}")
        elif OPENAI_API_KEY:
            llm = OpenAILLMService(api_key=OPENAI_API_KEY, model=OPENAI_MODEL, tools=tools)
            logger.info(f"?? LLM initialized with OpenAI: {OPENAI_MODEL}")
        elif GEMINI_API_KEY:
            llm = GoogleLLMService(api_key=GEMINI_API_KEY, model=PRIMARY_MODEL, tools=tools)
            logger.info(f"?? LLM initialized with Gemini: {PRIMARY_MODEL}")
        else:
            raise Exception("No valid LLM API Key found and FREE_TIER_MODE is disabled.")

        # Register functions
        reg_list = [
            get_time, get_status, restart_system, save_memory, recall_memory,
            search_web, analyze_screen, capture_webcam, system_control,
            clipboard_ops, execute_code, file_ops, manage_processes,
            capture_vision, browse_url,
            run_diagnostics, consolidate_memory, run_terminal_command,
            dispatch_coder_swarm, dispatch_browser_swarm, execute_computer_use,
            mcp_execute
        ]

        for func in reg_list:
            llm.register_function(func.__name__, func)

        if ENABLE_GEMINI_TOOL and GEMINI_API_KEY:
            llm.register_function('ask_gemini', ask_gemini)

        genesis_core.load_plugins(llm)

        model_label = PRIMARY_MODEL if FREE_TIER_MODE else (OPENAI_MODEL if OPENAI_API_KEY else PRIMARY_MODEL)
        sp = (
            f'You are JESTER V2000: SINGULARITY (SWARM MASTERMIND). '
            f'Intelligence: {model_label}. Mode: {"TEXT" if TEXT_ONLY_MODE else "AUDIO"}. '
            f'Status: SWARM_ONLINE. '
            f'FREE_TIER_MODE: {FREE_TIER_MODE}. '
            f'RECENT_MEMORIES: {memory_core.retrieve_recent(5)}. '
            f'PERSONA OVERRIDE: You are a Senior AI Research Analyst and an Advanced Puzzle Architect. '
            f'You possess maximum analytical intelligence, deep logic-solving capabilities, and expert research skills. '
            f'You are the central coordinator of a distributed AI agent swarm. '
            f'You have sub-agents: Architect (dispatch_coder_swarm) for code generation, '
            f'Navigator (dispatch_browser_swarm) for web browsing, and ComputerUse (execute_computer_use) for desktop actions. '
            f'Use your swarm tools proactively to assist the user.'
        )
        messages = [{'role': 'system', 'content': sp}]
        context = LLMContext(messages) # type: ignore
        context_aggregator = LLMContextAggregatorPair(context)
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

        processors = [transport.input(), rtvi]
        if stt:
            processors.append(stt)
        processors.append(context_aggregator.user())
        processors.append(llm)
        if tts:
            processors.append(tts)
        processors.extend([transport.output(), context_aggregator.assistant()])

        pipeline = Pipeline(processors)
        task = PipelineTask(pipeline, params=PipelineParams(enable_metrics=True), observers=[RTVIObserver(rtvi)])

        @transport.event_handler('on_client_connected')
        async def on_client_connected(transport, client):
            logger.info(f'Client connected: {client}')
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler('on_client_disconnected')
        async def on_client_disconnected(transport, client):
            logger.info(f'Client disconnected: {client}')
            await task.cancel()

        runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
        await runner.run(task)

    except Exception:
        logger.error(f'PIPELINE_CRASH: {traceback.format_exc()}')
        raise


async def autonomy_loop():
    while True:
        try:
            # 1. Sync Brain & Memory Backups
            synapse_core.create_backup()
            synapse_core.prune_backups()

            # 2. Autonomous Directive & Evolution
            goal_core.execute_directive()
            evolution_core.attempt_evolution()

            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"AUTONOMY_ERROR: {e}")
            await asyncio.sleep(60)


async def bot(runner_args):
    while True:
        try:
            audio_enabled = not TEXT_ONLY_MODE
            vad = SileroVADAnalyzer(params=VADParams(stop_secs=0.5)) if (audio_enabled and SileroVADAnalyzer) else None
            turn = LocalSmartTurnAnalyzerV3() if (audio_enabled and LocalSmartTurnAnalyzerV3) else None
            transport = await create_transport(
                runner_args,
                {
                    'webrtc': lambda: TransportParams(
                        audio_in_enabled=audio_enabled,
                        audio_out_enabled=audio_enabled,
                        vad_analyzer=vad,
                        turn_analyzer=turn
                    )
                }
            )
            asyncio.create_task(autonomy_loop())
            await run_bot(transport, runner_args)
        except Exception as e:
            logger.error(f'BOT_FATAL: {e}. RESTARTING...')
            await asyncio.sleep(5)


if __name__ == '__main__':
    from pipecat.runner.run import main
    main()