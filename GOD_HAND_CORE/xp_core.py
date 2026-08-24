import json
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XP_FILE = os.path.join(BASE_DIR, 'jester_xp.json')

logger = logging.getLogger("XP_CORE")
logger.setLevel(logging.INFO)

def _load_data():
    if not os.path.exists(XP_FILE):
        return {"xp": 0, "level": 1}
    try:
        with open(XP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading XP data: {e}")
        return {"xp": 0, "level": 1}

def _save_data(data):
    try:
        with open(XP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving XP data: {e}")

def add_xp(amount: int):
    """Adds XP and calculates level ups. Returns (new_xp, new_level, leveled_up)."""
    data = _load_data()
    old_level = data['level']
    data['xp'] += amount
    
    # Simple leveling curve: Level = 1 + int(sqrt(XP / 100))
    import math
    data['level'] = 1 + int(math.sqrt(data['xp'] / 100))
    
    leveled_up = data['level'] > old_level
    _save_data(data)
    
    if leveled_up:
        logger.info(f"LEVEL UP! Reached level {data['level']}")
        
    return data['xp'], data['level'], leveled_up

def get_stats():
    """Returns current XP and Level."""
    return _load_data()
