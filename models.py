from openenv.core.env_server.types import Action, Observation
from pydantic import Field
from typing import List, Optional
from pydantic import BaseModel


class Diff(BaseModel):
    id: str = Field(..., description="Unique diff id")
    diff_text: str = Field(..., description="Code changes shown as a diff")
    risk_hints: List[str] = Field(default_factory=list, description="Hints like sql_concat, missing_auth, etc.")
    has_tests: bool = Field(..., description="Whether the diff includes tests")
    touches_auth: bool = Field(..., description="Whether the diff touches authentication/security logic")


class CodeReviewObservation(Observation):
    current_diff: Diff
    steps_remaining: int = Field(..., description="Steps left in this episode")
    step: int = Field(default=0, description="Current step number")
    total_tasks: int = Field(default=0, description="Total number of tasks in this episode")
    feedback: str = Field(default="", description="Human-readable feedback on the last action")
    task_difficulty: str = Field(default="easy", description="Difficulty of the current task: easy | medium | hard")

    # Required for OpenEnv
    reward: float = Field(default=0.0, description="Reward from last action (0.0-1.0 range)")
    done: bool = Field(default=False, description="Episode termination flag")
    metadata: dict = Field(default_factory=dict, description="Extra debug info")


class CodeReviewAction(Action):
    action_type: str = Field(..., description="flag_bug | approve | ignore")
    severity: Optional[str] = Field(
        default=None,
        description="critical | medium | low -- optional severity classification"
    )
    comment: str = Field(
        default="",
        description="Optional explanation -- used for partial credit on hard tasks"
    )

    # Required for OpenEnv compatibility
    message: str = "ok"