import json
from duckduckgo_search import DDGS

print("TESTING NEW WEB UPLINK...")
try:
    # New recommended pattern
    results = DDGS().text("current world events", max_results=3)
    print(f"UPLINK_SUCCESS: {json.dumps(results)}")
except Exception as e:
    print(f"UPLINK_FAILURE: {str(e)}")
