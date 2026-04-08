# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Code Review Env Environment.

This module creates an HTTP server that exposes the CodeReviewEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 7860

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 7860 --workers 4

    # Or run directly:
    python -m server.app
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import CodeReviewAction, CodeReviewObservation
    from .code_review_env_environment import CodeReviewEnvironment
except ImportError:
    from code_review_env.models import CodeReviewAction, CodeReviewObservation
    from code_review_env.server.code_review_env_environment import CodeReviewEnvironment


# Create the app with web interface and README integration
app = create_app(
    CodeReviewEnvironment,
    CodeReviewAction,
    CodeReviewObservation,
    env_name="code_review_env",
    max_concurrent_envs=4,  # allows concurrent judge/agent sessions within 2vCPU/8GB limits
)


@app.get("/tasks", tags=["Environment Info"], summary="List all tasks with graders")
async def list_tasks():
    """Return the list of available tasks, their difficulties, and grader info."""
    return [
        {
            "id": "easy_code_review",
            "name": "Easy Code Review",
            "description": "Review 5 easy code diffs for hardcoded secrets, SQL f-string injection, division-by-zero without guard, unused imports, and a safe trusted utility function.",
            "difficulty": "easy",
            "grader": "server.graders.easy_grader",
            "time_limit_seconds": 600,
            "max_steps": 15
        },
        {
            "id": "medium_code_review",
            "name": "Medium Code Review",
            "description": "Review 5 medium-difficulty diffs covering missing authentication, plaintext password storage, off-by-one errors, and race conditions.",
            "difficulty": "medium",
            "grader": "server.graders.medium_grader",
            "time_limit_seconds": 600,
            "max_steps": 15
        },
        {
            "id": "hard_code_review",
            "name": "Hard Code Review",
            "description": "Review 5 hard diffs requiring deep security expertise: JWT signature bypass, insecure pickle deserialisation, ReDoS, and SSRF.",
            "difficulty": "hard",
            "grader": "server.graders.hard_grader",
            "time_limit_seconds": 600,
            "max_steps": 15
        }
    ]


def main(host: str = "0.0.0.0", port: int = 7860):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m code_review_env.server.app

    Args:
        host: Host address to bind to (default: "0.0.0.0")
        port: Port number to listen on (default: 7860)

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn code_review_env.server.app:app --workers 4
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
