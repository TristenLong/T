import os
import psutil
import datetime
import socket

def get_pc_stats():
    stats = []
    stats.append(f"--- PC STATUS REPORT [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    stats.append(f"Hostname: {socket.gethostname()}")
    stats.append(f"OS: {os.name} (win32)")
    
    # CPU
    stats.append(f"CPU Usage: {psutil.cpu_percent()}%")
    stats.append(f"CPU Cores: {psutil.cpu_count(logical=False)} (Physical), {psutil.cpu_count(logical=True)} (Logical)")
    
    # RAM
    mem = psutil.virtual_memory()
    stats.append(f"RAM: {mem.percent}% used ({mem.used // (1024**2)} MB / {mem.total // (1024**2)} MB)")
    
    # Disk
    disk = psutil.disk_usage('/')
    stats.append(f"Disk: {disk.percent}% used ({disk.free // (1024**3)} GB free)")
    
    # Miner (if exists)
    log_path = r"C:\Users\trist\Downloads\SRBMiner-Multi-3-1-1-win64\SRBMiner-Multi-3-1-1\Log.txt"
    if os.path.exists(log_path):
        stats.append("Mining Status: DETECTED")
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                last_lines = f.readlines()[-5:]
                stats.append("Recent Miner Logs:")
                stats.extend([f"  {line.strip()}" for line in last_lines])
        except:
            stats.append("  (Could not read miner log)")
    else:
        stats.append("Mining Status: NOT_FOUND")
        
    return "\n".join(stats)

if __name__ == "__main__":
    content = get_pc_stats()
    output_path = r"C:\Users\trist\PC_STATS.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"PC Stats generated at: {output_path}")
    print("\nContent:\n" + content)
