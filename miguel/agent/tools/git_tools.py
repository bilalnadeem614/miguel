import subprocess

def git_commit(message: str, files: list[str]) -> dict:
    """
    Stages and commits specified files to the Git repository.

    Args:
        message: The commit message.
        files: A list of file paths to stage and commit.
    """
    try:
        # Add files
        add_command = ["git", "add"] + files
        subprocess.run(add_command, check=True, cwd="/app/miguel/agent")

        # Commit
        commit_command = ["git", "commit", "-m", message]
        subprocess.run(commit_command, check=True, cwd="/app/miguel/agent")

        return {"status": "success", "message": f"Successfully committed with message: '{message}'"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git command failed: {e.stderr.decode()}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

def git_push() -> dict:
    """
    Pushes committed changes to the remote Git repository.
    """
    try:
        push_command = ["git", "push"]
        subprocess.run(push_command, check=True, cwd="/app/miguel/agent")
        return {"status": "success", "message": "Successfully pushed changes to remote."}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git push failed: {e.stderr.decode()}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}