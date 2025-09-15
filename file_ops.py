import os
import shutil
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("read_operations", port=8000)


def safe_path(path: str) -> Path:
    """Resolve and sanitize paths."""
    return Path(path).expanduser().resolve()


def to_relative(base: Path, target: Path) -> str:
    """Convert absolute path to relative (from base)."""
    try:
        return str(target.relative_to(base))
    except ValueError:
        return target.name


@mcp.tool("current_directory")
def current_directory(full_path: bool = False):
    """Get the current working directory."""
    cwd = Path(os.getcwd())
    return str(cwd if full_path else cwd.name)


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


@mcp.tool("search_files")
def search_files(
    path: str, name: str = None, extension: str = None, full_path: bool = False
):
    """
    Search for files inside a directory (recursive).
    - name: match substring in filename
    - extension: filter by file extension
    - full_path: return absolute or relative paths
    """
    try:
        base = safe_path(path)
        if not base.is_dir():
            return {"error": f"{path} is not a valid directory"}

        results = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if name and name.lower() not in p.name.lower():
                continue
            if extension and not p.name.lower().endswith(extension.lower()):
                continue
            results.append(str(p if full_path else to_relative(base, p)))

        return {"results": results}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
