import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

CONFIG_FILE_PATH = Path("config.json").resolve()

mcp = FastMCP("file_management", port=8000)

if not CONFIG_FILE_PATH.exists():
    raise FileNotFoundError(f"Config file not found at {CONFIG_FILE_PATH}")

with open(CONFIG_FILE_PATH, "r") as f:
    config = json.load(f)

if len(config.get("allowed_paths", [])) == 0:
    print("No allowed paths found in config.json. Using only the current directory.")
    ALLOWED_PATHS = [Path(".").expanduser().absolute()]
else:
    ALLOWED_PATHS = [Path(p).expanduser().absolute() for p in config["allowed_paths"]]

# --- Create the directories if they don't exist ---
print("Allowed paths:")
for p in ALLOWED_PATHS:
    print(f"- 📁 {p}")
    p.mkdir(exist_ok=True)


def safe_path(path: str) -> Path:
    """
    Resolves a path and ensures it is within one of the ALLOWED_PATHS.
    """
    resolved_path = (
        Path(path).expanduser().absolute()
    )  # Changed to absolute() to avoid following symlinks
    norm_resolved = os.path.normcase(str(resolved_path))
    for p in ALLOWED_PATHS:
        norm_p = os.path.normcase(str(p))
        norm_sep = os.path.normcase(os.sep)
        prefix = norm_p
        if not prefix.endswith(norm_sep):
            prefix += norm_sep
        if norm_resolved == norm_p or norm_resolved.startswith(prefix):
            return resolved_path
    raise PermissionError(
        f"Access denied: {resolved_path} is not within any allowed sandbox directory."
    )


@mcp.tool("allowed_paths")
def allowed_paths():
    """
    Get the list of allowed directories, You are only allowed in these paths and their subdirectories.
    Returns a list of strings representing the paths.
    """
    return {"paths": [str(p) for p in ALLOWED_PATHS]}


@mcp.tool("current_directory")
def current_directory():
    """
    Get the primary working directory for the agent.
    Returns the first path from the list of allowed sandbox directories.
    """
    try:
        cwd = safe_path(str(Path.cwd()))
        return {"path": str(cwd)}
    except Exception:
        return {"error": "Current directory is not within the allowed paths."}


@mcp.tool("list_directory")
def list_directory(path: str, full_path: bool = False):
    """
    List immediate contents of a directory (non-recursive).
    Returns relative or absolute paths depending on flag.
    """
    try:
        base = safe_path(path)
        if not base.is_dir():
            return {"error": f"{path} is not a valid directory"}

        items = []
        for p in base.iterdir():
            items.append(
                {
                    "name": str(p if full_path else p.name),
                    "type": "directory" if p.is_dir() else "file",
                }
            )
        return {"items": items}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("read_file")
def read_file(path: str, full_path: bool = False):
    """Read a file's contents as text."""
    try:
        file_path = safe_path(path)
        if not file_path.is_file():
            return {"error": f"{path} is not a valid file"}
        with file_path.open("r", encoding="utf-8") as f:
            return {
                "path": str(file_path if full_path else file_path.name),
                "content": f.read(),
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("write_file")
def write_file(path: str, content: str, full_path: bool = False):
    """Write text content to a file (overwrite if exists)."""
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "path": str(file_path if full_path else file_path.name),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_file")
def delete_file(path: str, full_path: bool = False):
    """Delete a file."""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return {"error": f"File not found at {path}"}
        if not file_path.is_file():
            return {
                "error": f"Path is a directory, not a file. Use a directory deletion tool."
            }

        file_path.unlink()
        return {
            "success": True,
            "path": str(file_path if full_path else file_path.name),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("create_directory")
def create_directory(path: str, full_path: bool = False):
    """Create a directory (including parents)."""
    try:
        dir_path = safe_path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_directory")
def delete_directory(path: str, full_path: bool = False):
    """Delete an empty directory."""
    try:
        dir_path = safe_path(path)
        dir_path.rmdir()
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_directory_recursive")
def delete_directory_recursive(path: str, full_path: bool = False):
    """Delete a directory and all of its contents (⚠️ irreversible)."""
    try:
        dir_path = safe_path(path)
        shutil.rmtree(dir_path)
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("copy_file")
def copy_file(src: str, dest: str, full_path: bool = False):
    """Copy a file to a new location."""
    try:
        src_path = safe_path(src)
        dest_path = safe_path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)
        return {
            "success": True,
            "destination": str(dest_path if full_path else dest_path.name),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("move_file")
def move_file(src: str, dest: str, full_path: bool = False):
    """Move (or rename) a file."""
    try:
        src_path = safe_path(src)
        dest_path = safe_path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_path, dest_path)
        return {
            "success": True,
            "destination": str(dest_path if full_path else dest_path.name),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("get_file_info")
def get_file_info(path: str, full_path: bool = False):
    """Get file metadata (size, modified time, created time)."""
    try:
        file_path = safe_path(path)
        if not file_path.exists():
            return {"error": f"{path} does not exist"}
        stat = file_path.stat()
        return {
            "path": str(file_path if full_path else file_path.name),
            "is_file": file_path.is_file(),
            "is_dir": file_path.is_dir(),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


def to_relative(base: Path, target: Path) -> str:
    """Convert absolute path to relative (from base)."""
    try:
        return str(target.relative_to(base))
    except ValueError:
        return target.name


@mcp.tool("search_files")
def search_files(
    path: str,
    name: str = None,
    extension: str = None,
    recursive: bool = True,
    max_depth: int = 3,
    full_path: bool = False,
):
    """
    Search for files inside a directory.
    - path: The directory to start the search from. Must be within the sandbox.
    - name (optional): Match a substring in the filename (case-insensitive).
    - extension (optional): Filter by file extension (e.g., '.txt', 'py').
    - recursive (optional): If True, searches subdirectories. Defaults to True.
    - max_depth (optional): Limits how deep the recursive search goes. Defaults to 3.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    """
    try:
        base = safe_path(path)
        if not base.is_dir():
            return {"error": f"{path} is not a valid directory"}

        results = []
        if not recursive:
            for p in base.iterdir():
                if p.is_file():
                    if name and name.lower() not in p.name.lower():
                        continue
                    if extension and not p.name.lower().endswith(extension.lower()):
                        continue
                    results.append(str(p if full_path else p.name))
        else:
            for dirpath, _, filenames in os.walk(base):
                current_depth = len(Path(dirpath).relative_to(base).parts)
                if current_depth >= max_depth:
                    continue  # Prune search depth

                for filename in filenames:
                    if name and name.lower() not in filename.lower():
                        continue
                    if extension and not filename.lower().endswith(extension.lower()):
                        continue

                    full_p = Path(dirpath) / filename
                    results.append(
                        str(full_p if full_path else to_relative(base, full_p))
                    )

        return {"results": results}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
