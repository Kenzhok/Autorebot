"""
graders.py — Root-level re-export of Code Review Environment graders.

This file exists at the repo root so that the OpenEnv judge can import
grader functions WITHOUT needing the package to be pip-installed first.

The openenv.yaml references these as:  graders:easy_grader
which resolves to this file when openenv validate runs from the repo root.

All grader logic is implemented in server/graders.py.
"""
import sys
import os

# Ensure server/ is importable when running from repo root
_server_path = os.path.join(os.path.dirname(__file__), "server")
if _server_path not in sys.path:
    sys.path.insert(0, _server_path)

try:
    # Installed package path (Docker / pip install -e .)
    from code_review_env.server.graders import easy_grader, medium_grader, hard_grader
except ImportError:
    try:
        # Repo root path (openenv validate without install)
        from server.graders import easy_grader, medium_grader, hard_grader
    except ImportError:
        # Direct server/ path (last resort)
        from graders import easy_grader, medium_grader, hard_grader  # type: ignore[no-redef]

__all__ = ["easy_grader", "medium_grader", "hard_grader"]
