import json
from duckduckgo_search import DDGS

print("TESTING WEB UPLINK...")
try:
    with DDGS() as ddgs:
        results = [r for r in ddgs.text("current world news", max_results=3)]
        print(f"UPLINK_SUCCESS: {json.dumps(results)}")
except Exception as e:
    print(f"UPLINK_CRITICAL_FAILURE: {str(e)}")
