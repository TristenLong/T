import time
import psutil

def _self_check() -> str:
    try:
        boot_time = psutil.boot_time()
        if boot_time > 0:
            return 'OK'
        return 'FAIL: Invalid boot time'
    except Exception as e:
        return f'FAIL: {str(e)}'

def uptime_tool(value: str = '') -> str:
    try:
        boot_time = psutil.boot_time()
        current_time = time.time()
        uptime_seconds = int(current_time - boot_time)

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0 or days > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        uptime_string = ", ".join(parts)
        return f"System uptime: {uptime_string} (weather-independent)"
    except Exception as e:
        return f"Error calculating uptime: {str(e)}"