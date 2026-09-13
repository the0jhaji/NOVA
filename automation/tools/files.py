"""
NOVA Voice Assistant - File Tools
create_file / move_file / copy_file / rename_file / search_files / delete_file

All operations are parameterised shutil/os calls — NOVA never builds a shell
command. Protected-root deletions are blocked earlier by the safety layer.
"""

import fnmatch
import os
import shutil
from typing import Optional

from config import config
from utils.logger import log
from automation.result import ToolResult
from automation.paths import resolve_user_path, user_home
from automation.verifier import path_is_file, path_is_dir, path_gone


def _parent_base(location: str) -> str:
    if location:
        base = resolve_user_path(location)
        if path_is_dir(base):
            return base
        return os.path.dirname(base)
    return os.path.expanduser("~/Desktop")


def create_file(name: str, location: str = "", content: str = "") -> ToolResult:
    """Create a new file with optional text content."""
    base = _parent_base(location)
    path = resolve_user_path(name, base=base)
    if path_is_file(path):
        return ToolResult(
            tool="create_file", success=False, verified=False,
            message=f"A file named {os.path.basename(path)} already exists there.",
            details={"path": path},
        )
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(content or "")
    except Exception as e:
        log.error("create_file failed: %s", e)
        return ToolResult(
            tool="create_file", success=False, verified=False,
            message=f"I couldn't create that file.",
            details={"error": str(e), "path": path},
        )
    return ToolResult(
        tool="create_file", success=True, verified=path_is_file(path),
        message=f"Created {os.path.basename(path)}.",
        details={"path": path},
    )


def _resolve_source(source: str) -> str:
    if os.path.isabs(source):
        return source
    return resolve_user_path(source, base=os.path.expanduser("~/Desktop"))


def _target_dir(destination: str) -> str:
    """Resolve a spoken destination to a directory (creating path implicitly)."""
    if not destination:
        return os.path.expanduser("~/Desktop")
    if os.path.isabs(destination):
        return destination
    return resolve_user_path(destination, base=os.path.expanduser("~/Desktop"))


def move_file(source: str, destination: str) -> ToolResult:
    src = _resolve_source(source)
    if not os.path.exists(src):
        return ToolResult(
            tool="move_file", success=False, verified=False,
            message=f"I couldn't move that because {os.path.basename(src)} wasn't found.",
            details={"source": src},
        )
    dst_dir = _target_dir(destination)
    try:
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst_dir)
    except Exception as e:
        log.error("move_file failed: %s", e)
        return ToolResult(
            tool="move_file", success=False, verified=False,
            message=f"I couldn't move {os.path.basename(src)}.",
            details={"error": str(e)},
        )
    moved = os.path.join(dst_dir, os.path.basename(src))
    ok = path_is_file(moved) or path_is_dir(moved)
    return ToolResult(
        tool="move_file", success=ok, verified=ok and path_gone(src),
        message=f"Moved {os.path.basename(src)} to {os.path.basename(dst_dir)}."
                if ok else f"I couldn't move {os.path.basename(src)}.",
        details={"source": src, "destination": moved},
    )


def copy_file(source: str, destination: str) -> ToolResult:
    src = _resolve_source(source)
    if not os.path.exists(src):
        return ToolResult(
            tool="copy_file", success=False, verified=False,
            message=f"I couldn't copy that because {os.path.basename(src)} wasn't found.",
            details={"source": src},
        )
    dst_dir = _target_dir(destination)
    try:
        os.makedirs(dst_dir, exist_ok=True)
        if path_is_dir(src):
            target = os.path.join(dst_dir, os.path.basename(src))
            shutil.copytree(src, target, dirs_exist_ok=True)
            copied = target
        else:
            copied = shutil.copy2(src, dst_dir)
    except Exception as e:
        log.error("copy_file failed: %s", e)
        return ToolResult(
            tool="copy_file", success=False, verified=False,
            message=f"I couldn't copy {os.path.basename(src)}.",
            details={"error": str(e)},
        )
    ok = os.path.exists(copied)
    return ToolResult(
        tool="copy_file", success=ok, verified=ok,
        message=f"Copied {os.path.basename(src)} to {os.path.basename(dst_dir)}.",
        details={"source": src, "destination": copied},
    )


def rename_file(source: str, new_name: str) -> ToolResult:
    src = _resolve_source(source)
    if not os.path.exists(src):
        return ToolResult(
            tool="rename_file", success=False, verified=False,
            message=f"I couldn't rename that because {os.path.basename(src)} wasn't found.",
            details={"source": src},
        )
    dst = os.path.join(os.path.dirname(src), new_name)
    try:
        os.rename(src, dst)
    except Exception as e:
        log.error("rename_file failed: %s", e)
        return ToolResult(
            tool="rename_file", success=False, verified=False,
            message=f"I couldn't rename {os.path.basename(src)}.",
            details={"error": str(e)},
        )
    ok = os.path.exists(dst) and path_gone(src)
    return ToolResult(
        tool="rename_file", success=ok, verified=ok,
        message=f"Renamed {os.path.basename(src)} to {new_name}.",
        details={"source": src, "destination": dst},
    )


def search_files(query: str = "*", location: str = "") -> ToolResult:
    """Search for files by name pattern (case-insensitive) under a root."""
    root = resolve_user_path(location) if location else (config.automation.search_root or user_home())
    pattern = (query or "*").lower()
    if not any(ch in pattern for ch in "*?["):
        pattern = f"*{pattern}*"
    matches: list[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # keep the walk shallow-ish: cap to avoid minutes-long scans
            if dirpath.count(os.sep) - root.count(os.sep) > 4:
                dirnames[:] = []
                continue
            for fn in filenames:
                if fnmatch.fnmatch(fn.lower(), pattern):
                    matches.append(os.path.join(dirpath, fn))
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
    except Exception as e:
        log.error("search_files failed: %s", e)
        return ToolResult(
            tool="search_files", success=False, verified=False,
            message="I couldn't search there.",
            details={"error": str(e), "root": root},
        )
    if not matches:
        return ToolResult(
            tool="search_files", success=True, verified=True,
            message=f"No files match {query or 'that pattern'}.",
            details={"root": root, "count": 0},
        )
    names = sorted({os.path.basename(p) for p in matches[:10]})
    sample = ", ".join(names[:5])
    return ToolResult(
        tool="search_files", success=True, verified=True,
        message=f"Found {len(matches)} matching file{'s' if len(matches) != 1 else ''}{': ' + sample if sample else ''} in {os.path.basename(root)}.",
        details={"root": root, "count": len(matches), "matches": matches[:50]},
    )


def delete_file(path: str, is_dir: bool = False) -> ToolResult:
    """Delete a file (or empty folder chain). Requires confirmation upstream."""
    full = path if os.path.isabs(path) else os.path.join(os.path.expanduser("~/Desktop"), path)
    if not os.path.exists(full):
        return ToolResult(
            tool="delete_file", success=False, verified=False,
            message=f"I couldn't delete that because {os.path.basename(full)} wasn't found.",
            details={"path": full},
        )
    try:
        if is_dir:
            shutil.rmtree(full)
        else:
            os.remove(full)
    except Exception as e:
        log.error("delete_file failed: %s", e)
        return ToolResult(
            tool="delete_file", success=False, verified=False,
            message=f"I couldn't delete {os.path.basename(full)}.",
            details={"error": str(e), "path": full},
        )
    return ToolResult(
        tool="delete_file", success=True, verified=path_gone(full),
        message=f"Deleted {os.path.basename(full)}.",
        details={"path": full},
    )