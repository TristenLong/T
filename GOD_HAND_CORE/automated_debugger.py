import os
import subprocess


def run_diagnostics(target_dir: str) -> str:
    """
    Runs automated static analysis using flake8 and pylint on all python files in the directory.
    Returns a formatted string report for JESTER to read and act upon.
    """
    if not os.path.exists(target_dir):
        return f"DEBUG_ERROR: Directory {target_dir} not found."
    
    report = f"--- AUTODEBUG REPORT FOR {target_dir} ---\n\n"
    
    # Run flake8 (Syntax and stylistic errors)
    try:
        # Check if flake8 is available
        result = subprocess.run(
            ["python", "-m", "flake8", target_dir, "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            report += "=== CRITICAL SYNTAX ERRORS (FLAKE8) ===\n"
            report += result.stdout + "\n"
            report += result.stderr + "\n"
        else:
            report += "=== FLAKE8: No critical syntax errors found. ===\n\n"
    except Exception as e:
        report += f"Flake8 execution failed: {e}\n\n"

    # Run pylint (Deep static analysis)
    try:
        result = subprocess.run(
            ["python", "-m", "pylint", target_dir, "--disable=all", "--enable=E,F", "--output-format=text"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            report += "=== DEEP LOGIC ERRORS (PYLINT) ===\n"
            report += result.stdout + "\n"
        else:
            report += "=== PYLINT: No critical logic errors found. ===\n"
    except Exception as e:
        report += f"Pylint execution failed: {e}\n"

    return report

def auto_heal(file_path: str, instructions: str) -> str:
    """
    In the future, this function will be called by JESTER to automatically apply AST transformations 
    or AI-generated diffs based on the diagnostics report.
    For now, it acts as a stub to inform the agent to use its CODE tools to fix the file.
    """
    return f"AUTOHEAL_PENDING: Please use the READ_FILE and CODE tools to apply fixes to {file_path} based on: {instructions}"
