import math

def format_size_tool(value: str = '') -> str:
    try:
        clean_val = value.strip()
        if not clean_val:
            return "Error: Empty input provided."
        
        num = float(clean_val)
        if num < 0:
            return "Error: Negative numbers cannot be sized."
        
        if num == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']
        i = int(math.floor(math.log(num, 1024)))
        i = min(i, len(units) - 1)
        
        p = math.pow(1024, i)
        s = round(num / p, 2)
        
        return f"{s} {units[i]}"
    except (ValueError, TypeError, OverflowError) as e:
        return f"Error: Invalid numeric input ({e})."

def _self_check() -> str:
    try:
        test_val = "1048576"
        res = format_size_tool(test_val)
        if "1.0 MB" in res:
            return "OK"
        return f"FAIL: Unexpected output for 1MB conversion: {res}"
    except Exception as e:
        return f"FAIL: Exception during self check: {str(e)}"