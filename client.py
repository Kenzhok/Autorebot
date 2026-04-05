# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Code Review Env Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import CodeReviewAction, CodeReviewObservation, Diff
except ImportError:
    from models import CodeReviewAction, CodeReviewObservation, Diff


class CodeReviewEnv(
    EnvClient[CodeReviewAction, CodeReviewObservation, State]
):
    """
    Client for the Code Review Env Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> with CodeReviewEnv(base_url="http://localhost:8000") as env:
        ...     result = env.reset()
        ...     print(result.observation.current_diff.diff_text)
        ...
        ...     action = CodeReviewAction(action_type="flag_bug", comment="SQL injection risk")
        ...     result = env.step(action)
        ...     print(result.observation.feedback)
        ...     print(result.reward)

    Example with Docker:
        >>> client = CodeReviewEnv.from_docker_image("code_review_env-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     action = CodeReviewAction(action_type="approve")
        ...     result = client.step(action)
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: CodeReviewAction) -> Dict:
        """
        Convert CodeReviewAction to JSON payload for step message.

        Args:
            action: CodeReviewAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "action_type": action.action_type,
            "severity": action.severity,
            "comment": action.comment,
            "message": action.message,
        }

    def _parse_result(self, payload: Dict) -> StepResult[CodeReviewObservation]:
        """
        Parse server response into StepResult[CodeReviewObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with CodeReviewObservation
        """
        obs_data = payload.get("observation", {})

        # Parse the nested Diff object
        diff_data = obs_data.get("current_diff", {})
        diff = Diff(
            id=diff_data.get("id", ""),
            diff_text=diff_data.get("diff_text", ""),
            risk_hints=diff_data.get("risk_hints", []),
            has_tests=diff_data.get("has_tests", False),
            touches_auth=diff_data.get("touches_auth", False),
        )

        observation = CodeReviewObservation(
            current_diff=diff,
            steps_remaining=obs_data.get("steps_remaining", 0),
            step=obs_data.get("step", 0),
            total_tasks=obs_data.get("total_tasks", 0),
            feedback=obs_data.get("feedback", ""),
            task_difficulty=obs_data.get("task_difficulty", "easy"),
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
