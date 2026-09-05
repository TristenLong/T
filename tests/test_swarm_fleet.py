import os
import pytest
import requests

BASE_URL = 'http://127.0.0.1:5000'
TOKEN_FILE = os.path.join(os.path.dirname(__file__), '..', 'GOD_HAND_CORE', '.jester_token')

@pytest.fixture
def auth_headers():
    token = open(TOKEN_FILE).read().strip() if os.path.exists(TOKEN_FILE) else ''
    return {'X-Jester-Token': token}

def test_matrix_status_endpoint(auth_headers):
    res = requests.get(f'{BASE_URL}/api/matrix_status', headers=auth_headers, timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert 'cpu' in data
    assert 'ram' in data
    assert 'model' in data
    assert data['ram'] > 0

def test_stats_endpoint(auth_headers):
    res = requests.get(f'{BASE_URL}/api/stats', headers=auth_headers, timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert 'level' in data
    assert 'xp' in data

def test_swarm_bots_endpoint(auth_headers):
    res = requests.get(f'{BASE_URL}/api/swarm/bots', headers=auth_headers, timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert 'bots' in data
    bot_ids = [b['id'] for b in data['bots']]
    for expected in ['jester', 'claude', 'gemini', 'brutal_critic', 'codex']:
        assert expected in bot_ids

def test_ram_optimizer_endpoint(auth_headers):
    res = requests.get(f'{BASE_URL}/api/sys/optimize_ram', headers=auth_headers, timeout=10)
    assert res.status_code == 200
    data = res.json()
    assert data.get('status') == 'SUCCESS'
    assert 'ram_before_mb' in data
    assert 'ram_after_mb' in data
    assert 'freed_mb' in data

def test_sentry_scan_endpoint(auth_headers):
    res = requests.get(f'{BASE_URL}/api/sentry/scan', headers=auth_headers, timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert 'status' in data
    assert 'alert' in data
    assert 'cpu' in data
    assert 'ram' in data

def test_swarm_agent_chat(auth_headers):
    res = requests.post(f'{BASE_URL}/api/swarm/agent_chat', headers=auth_headers, json={'bot_id': 'codex', 'message': 'ping'}, timeout=35)
    assert res.status_code == 200
    data = res.json()
    assert 'reply' in data
    assert len(data['reply']) > 0

def test_security_unauthorized_rejection():
    # Verify that requests without token to protected endpoint are gated appropriately
    res = requests.post(f'{BASE_URL}/api/swarm/agent_chat', json={'bot_id': 'codex', 'message': 'test'}, timeout=5)
    assert res.status_code in [401, 403]

