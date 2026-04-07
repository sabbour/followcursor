"""MkDocs Macros plugin hook — injects app version into all doc pages.

Usage in markdown:
    Current release: **{{ version }}**
"""

import ast
import os
from typing import Any


def _read_version(version_file: str) -> str:
    """Read ``__version__`` from ``version.py`` without executing code."""
    with open(version_file, encoding="utf-8") as f:
        module = ast.parse(f.read(), filename=version_file)

    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value

    raise ValueError(f"Could not find a string literal __version__ in {version_file}")


def define_env(env: Any) -> None:
    """Called by mkdocs-macros-plugin to populate template variables."""
    version_file = os.path.join(
        os.path.dirname(__file__), "..", "..", "followcursor", "app", "version.py"
    )
    env.variables["version"] = _read_version(version_file)
