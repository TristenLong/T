import os
import re
import statistics
import datetime

LOG_PATH = r"C:\Users\trist\Downloads\SRBMiner-Multi-3-1-1-win64\SRBMiner-Multi-3-1-1\Log.txt"

def analyze_miner():
    if not os.path.exists(LOG_PATH): return {"status": "OFFLINE", "error": "Log file missing"}
    stats = {"status": "IDLE", "hashrates": [], "algos": set(), "valid": 0, "rejected": 0}
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()[-2000:]
        for line in lines:
            if "Hashrate" in line:
                m = re.search(r"Hashrate:\s+([\d\.]+)", line)
                if m: stats["hashrates"].append(float(m.group(1)))
                stats["status"] = "MINING"
            if "Algorithm" in line:
                m = re.search(r"Algorithm:\s+(\w+)", line)
                if m: stats["algos"].add(m.group(1))
            if "accepted" in line.lower(): stats["valid"] += 1
            if "rejected" in line.lower(): stats["rejected"] += 1
        
        if stats["hashrates"]:
            stats["avg"] = statistics.mean(stats["hashrates"])
            stats["max"] = max(stats["hashrates"])
        stats["algos"] = list(stats["algos"])
        return stats
    except Exception as e: return {"error": str(e)}
