"""MkDocs Macros plugin hook — injects app version into all doc pages.

Usage in markdown:
    Current release: **{{ version }}**
"""

import os


def define_env(env):
    """Called by mkdocs-macros-plugin to populate template variables."""
    version_file = os.path.join(
        os.path.dirname(__file__), "..", "..", "followcursor", "app", "version.py"
    )
    namespace: dict = {}
    with open(version_file) as f:
        exec(f.read(), namespace)  # noqa: S102
    env.variables["version"] = namespace["__version__"]
