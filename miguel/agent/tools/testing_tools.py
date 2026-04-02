import subprocess
import os

def run_pytest(target_path: str) -> dict:
    """
    Runs pytest on a specified file or directory.

    Args:
        target_path: The file or directory path to run pytest on.

    Returns:
        A dictionary with the success status, output, and error (if any).
    """
    try:
        command = ["pytest", target_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "output": e.stdout, "error": e.stderr}
    except FileNotFoundError:
        return {"success": False, "error": "pytest command not found. Make sure pytest is installed."}

def run_code_and_compare_output(code: str, expected_output: str) -> dict:
    """
    Executes a Python code snippet and compares its standard output to an expected string.

    Args:
        code: The Python code snippet to execute.
        expected_output: The expected standard output of the code.

    Returns:
        A dictionary with the success status, actual output, expected output, and a match status.
    """
    try:
        # Save code to a temporary file
        temp_file = "temp_code_for_testing.py"
        with open(temp_file, "w") as f:
            f.write(code)

        command = ["python", temp_file]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        actual_output = result.stdout.strip()
        os.remove(temp_file)  # Clean up the temporary file

        match = (actual_output == expected_output.strip())
        return {
            "success": True,
            "actual_output": actual_output,
            "expected_output": expected_output.strip(),
            "match": match,
            "message": "Output matches expected." if match else "Output does not match expected."
        }
    except subprocess.CalledProcessError as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return {"success": False, "error": e.stderr, "output": e.stdout}
    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return {"success": False, "error": str(e)}

def run_agent_tests() -> dict:
    """
    Runs pytest on Miguel's own agent directory.

    Returns:
        A dictionary with the success status, output, and error (if any).
    """
    # Assuming the agent directory is the current working directory or accessible relative path
    # For now, let's assume it's the current directory where the script is run from.
    # A more robust solution might involve getting the agent_dir from config or core.py.
    try:
        command = ["pytest", "."] # Run pytest in the current directory
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "output": e.stdout, "error": e.stderr}
    except FileNotFoundError:
        return {"success": False, "error": "pytest command not found. Make sure pytest is installed."}