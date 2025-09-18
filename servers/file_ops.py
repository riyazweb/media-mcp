import os
import shutil
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

from config.settings import load_config_loud
import utils.image_search_utils as image_utils

mcp = FastMCP("file_management", port=8000)

config = load_config_loud()
# --- Create the directories if they don't exist ---
print("Allowed paths:")
for p in config["allowed_paths"]:
    print(f"- 📁 {p}")
    p.mkdir(exist_ok=True)

print("Media indexed paths:")
for p in config["media_index_allowed_paths"]:
    print(f"- 📁 {p}")


def safe_path(path: str) -> Path:
    """
    Resolves a path and ensures it is within one of the ALLOWED_PATHS.
    """
    resolved_path = (
        Path(path).expanduser().absolute()
    )  # Changed to absolute() to avoid following symlinks
    norm_resolved = os.path.normcase(str(resolved_path))
    for p in config["allowed_paths"]:
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
    Returns:
    - A list of strings representing the paths.
    """
    return {
        "allowed_paths": [str(p) for p in config["allowed_paths"]],
        "media_indexed_paths": [str(p) for p in config["media_index_allowed_paths"]],
    }


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
    Arguments:
    - path: The path to the directory to list.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A list of dictionaries containing the name and type of each item.
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
    """
    Read a file's contents as text.
    Arguments:
    - path: The path to the file to read.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary containing the path and the contents of the file.
    """
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
def write_file(
    path: str,
    content: str,
    append: bool = False,
    overwrite: bool = False,
    full_path: bool = False,
):
    """
    Write text content to a file (overwrite if exists).
    Arguments:
    - path: The path to the file to write to.
    - content: The text content to write to the file.
    - append (optional): If True, appends to the file instead of overwriting. Defaults to False.
    - overwrite (optional): If True, overwrites the file if it exists. Defaults to False.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
    try:
        file_path = safe_path(path)
        if (not overwrite) and file_path.exists():
            return {"error": f"File already exists at {path}"}
        file_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with file_path.open(mode, encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "path": str(file_path if full_path else file_path.name),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_file")
def delete_file(path: str, full_path: bool = False):
    """
    Delete a file.
    Arguments:
    - path: The path to the file to delete.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
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
    """
    Create a directory (including parents).
    Arguments:
    - path: The path to the directory to create.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
    try:
        dir_path = safe_path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_directory")
def delete_directory(path: str, full_path: bool = False):
    """
    Delete an empty directory.
    Arguments:
    - path: The path to the directory to delete.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
    try:
        dir_path = safe_path(path)
        dir_path.rmdir()
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("delete_directory_recursive")
def delete_directory_recursive(path: str, full_path: bool = False):
    """
    Delete a directory and all of its contents (⚠️ irreversible).
    Arguments:
    - path: The path to the directory to delete.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
    try:
        dir_path = safe_path(path)
        shutil.rmtree(dir_path)
        return {"success": True, "path": str(dir_path if full_path else dir_path.name)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool("copy_file")
def copy_file(src: str, dest: str, full_path: bool = False):
    """
    Copy a file to a new location.
    Arguments:
    - src: The path to the file to copy.
    - dest: The path to the new location for the file.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
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
    """
    Move (or rename) a file.
    Arguments:
    - src: The path to the file to move.
    - dest: The path to the new location for the file.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary indicating success or failure.
    """
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
    """
    Get file metadata (size, modified time, created time).
    Arguments:
    - path: The path to the file to get metadata for.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A dictionary containing the path, file type, size, modified time, and created time.
    """
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
    Arguments:
    - path: The directory to start the search from. Must be within the sandbox.
    - name (optional): Match a substring in the filename (case-insensitive).
    - extension (optional): Filter by file extension (e.g., '.txt', 'py').
    - recursive (optional): If True, searches subdirectories. Defaults to True.
    - max_depth (optional): Limits how deep the recursive search goes. Defaults to 3.
    - full_path (optional): If True, returns absolute paths. Defaults to False (relative).
    Returns:
    - A list of dictionaries containing the name, type, and path of each file.
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


# Image related tools
@mcp.tool("search_image_by_text")
def search_image_by_text(query: str, top_k: int = 5):
    """
    Search for images by text query semantically.
    Arguments:
    - query: The text query to search for.
    - top_k (optional): The number of results to return. Defaults to 5.
    Returns:
    - A list of absolute paths to the images.
    """
    res = image_utils.search_by_text(query, top_k)
    return [str(p[2]) for p in res]


@mcp.tool("search_by_image")
def search_by_image(path: str, top_k: int = 5):
    """
    Search for similar images by providing the path to an image.
    Arguments:
    - path: The path to the image to search for.
    - top_k (optional): The number of results to return. Defaults to 5.
    Returns:
    - A list containing the absolute paths to the images.
    """
    res = image_utils.search_by_image(path, top_k)
    return {"results": [str(p[2]) for p in res]}


if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"Server error: {e}")
