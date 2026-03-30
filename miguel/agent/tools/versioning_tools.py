import os
import datetime

def versioned_write_file(content: str, directory: str = None, extension: str = None, filename: str = None) -> dict:
    """
    Writes content to a file, creating a timestamped backup of the previous version.
    """
    # Determine the full path of the file to be written
    if directory:
        base_dir = directory
    else:
        base_dir = "/app/miguel/agent"

    if filename:
        if not filename.endswith(f".{extension}") and extension:
            file_path = os.path.join(base_dir, f"{filename}.{extension}")
        else:
            file_path = os.path.join(base_dir, filename)
    elif extension:
        # Generate a UUID filename if only extension is provided
        import uuid
        file_path = os.path.join(base_dir, f"{uuid.uuid4()}.{extension}")
    else:
        # Fallback if neither filename nor extension is provided, use a default name for now
        # In a real scenario, this should likely raise an error or have a more robust default
        file_path = os.path.join(base_dir, "untitled.txt")

    # Create .versions directory if it doesn't exist
    versions_dir = os.path.join(os.path.dirname(file_path), ".versions")
    os.makedirs(versions_dir, exist_ok=True)

    # If the file exists, create a backup
    if os.path.exists(file_path):
        try:
            current_content_response = default_api.read_file(file_name=file_path)
            if current_content_response and "read_file_response" in current_content_response:
                current_content = current_content_response["read_file_response"]["result"]
            else:
                current_content = ""
        except Exception as e:
            print(f"Error reading existing file for backup: {e}")
            current_content = ""

        if current_content:
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            backup_filename = f"{os.path.basename(file_path)}.{timestamp}.bak"
            backup_path = os.path.join(versions_dir, backup_filename)
            try:
                default_api.write_file(content=current_content, filename=backup_path)
                print(f"Backed up current content to {backup_path}")
            except Exception as e:
                return {"error": f"Failed to create backup: {e}"}

    # Write the new content to the original file
    try:
        write_response = default_api.write_file(content=content, filename=file_path)
        return write_response
    except Exception as e:
        return {"error": f"Failed to write new content: {e}"}

def rollback_file(file_path: str, version_timestamp: str) -> dict:
    """
    Rolls back a file to a specific version based on its timestamp.
    """
    versions_dir = os.path.join(os.path.dirname(file_path), ".versions")
    backup_filename = f"{os.path.basename(file_path)}.{version_timestamp}.bak"
    backup_path = os.path.join(versions_dir, backup_filename)

    if not os.path.exists(backup_path):
        return {"error": f"Version {version_timestamp} not found for file {file_path}"}

    try:
        version_content_response = default_api.read_file(file_name=backup_path)
        if version_content_response and "read_file_response" in version_content_response:
            version_content = version_content_response["read_file_response"]["result"]
        else:
            return {"error": f"Failed to read content of versioned file {backup_path}"}
    except Exception as e:
        return {"error": f"Error reading versioned file: {e}"}

    try:
        write_response = default_api.write_file(content=version_content, filename=file_path, overwrite=True)
        return write_response
    except Exception as e:
        return {"error": f"Failed to rollback file {file_path}: {e}"}