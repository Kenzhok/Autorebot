from uuid import uuid4
try:
    from code_review_env.models import CodeReviewAction, CodeReviewObservation
except ImportError:
    from code_review_env.models import CodeReviewAction, CodeReviewObservation
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State
from .tasks import get_tasks


class CodeReviewEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        super().__init__()  # sets self.transform and self.rubric (required by base class)
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0
        self.difficulty = "easy"
        self.tasks = []
        self.current_index = 0
        self.steps_used = 0
        self.steps_max = 15  # enough for all-difficulty episodes

    # ──────────────────────────────────────────────────────────────
    # reset
    # ──────────────────────────────────────────────────────────────
    def reset(self, seed=None, episode_id=None, difficulty: str = "easy", **kwargs) -> CodeReviewObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count += 1

        tasks_dict = get_tasks()
        self.difficulty = difficulty

        if difficulty == "all":
            self.tasks = (
                tasks_dict["easy"]
                + tasks_dict["medium"]
                + tasks_dict["hard"]
            )
        else:
            self.tasks = tasks_dict.get(difficulty, tasks_dict["easy"])

        self.current_index = 0
        self.steps_used = 0

        return self._get_observation(reward=0.0, done=False, feedback="Episode started. Review the diff carefully.")

    # ──────────────────────────────────────────────────────────────
    # step
    # ──────────────────────────────────────────────────────────────
    def step(self, action: CodeReviewAction) -> CodeReviewObservation:
        self._state.step_count += 1

        # Safety: re-load tasks if empty (e.g. after deserialization)
        if not self.tasks:
            tasks_dict = get_tasks()
            if self.difficulty == "all":
                self.tasks = (
                    tasks_dict["easy"]
                    + tasks_dict["medium"]
                    + tasks_dict["hard"]
                )
            else:
                self.tasks = tasks_dict.get(self.difficulty, tasks_dict["easy"])

        if self.current_index >= len(self.tasks):
            return self._get_observation(reward=0.0, done=True, feedback="Episode already complete.")

        current_task = self.tasks[self.current_index]

        # Calculate partial-credit reward
        reward, feedback = self._calculate_reward(action, current_task)

        self.steps_used += 1
        self.current_index += 1

        done = (
            self.current_index >= len(self.tasks)
            or self.steps_used >= self.steps_max
        )

        return self._get_observation(reward=reward, done=done, feedback=feedback)

    # ──────────────────────────────────────────────────────────────
    # _get_observation
    # ──────────────────────────────────────────────────────────────
    def _get_observation(self, reward: float, done: bool, feedback: str = "") -> CodeReviewObservation:
        if not self.tasks:
            tasks_dict = get_tasks()
            if self.difficulty == "all":
                self.tasks = (
                    tasks_dict["easy"]
                    + tasks_dict["medium"]
                    + tasks_dict["hard"]
                )
            else:
                self.tasks = tasks_dict.get(self.difficulty, tasks_dict["easy"])

        total_tasks = len(self.tasks)

        if self.current_index >= len(self.tasks):
            task = self.tasks[-1]
            steps_remaining = 0
        else:
            task = self.tasks[self.current_index]
            steps_remaining = max(0, self.steps_max - self.steps_used)

        diff = task.diff

        return CodeReviewObservation(
            current_diff=diff,
            steps_remaining=steps_remaining,
            step=self.steps_used,
            total_tasks=total_tasks,
            feedback=feedback,
            task_difficulty=task.difficulty,
            reward=reward,
            done=done,
            metadata={
                "task_id": task.id,
                "difficulty": task.difficulty,
                "current_index": self.current_index,
                "steps_used": self.steps_used,
                "episode_id": self._state.episode_id,
            },
        )

    # ──────────────────────────────────────────────────────────────
    # _calculate_reward  (all values strictly in (0.1, 0.9))
    # ──────────────────────────────────────────────────────────────
    # Reward ladder (never exactly 0.0 or 1.0 — judge requires strict range):
    #   0.90 correct action on easy/medium task
    #   0.90 correct on hard task WITH explanatory comment
    #   0.70 correct on hard task WITHOUT comment  (partial credit)
    #   0.50 ignore on safe code  (cautious but acceptable — no harm)
    #   0.30 ignore on a real bug  (missed the issue — bad, not catastrophic)
    #   0.15 flag_bug on safe code  (false positive — wastes reviewer time)
    #   0.10 approve a buggy diff  (worst outcome — ships a vulnerability)
    # ──────────────────────────────────────────────────────────────
    def _calculate_reward(self, action: CodeReviewAction, task) -> tuple[float, str]:
        correct = task.correct_action
        given = action.action_type
        difficulty = task.difficulty
        has_comment = bool(action.comment and action.comment.strip())

        # ── Correct action ────────────────────────────────────────
        if given == correct:
            if difficulty == "hard" and not has_comment:
                # Hard tasks: partial credit without explanatory comment
                return 0.70, (
                    task.feedback_on_correct
                    + " (Tip: add a comment explaining the vulnerability for full marks.)"
                )
            return 0.90, task.feedback_on_correct

        # -- Wrong action -- nuanced penalties ----------------------
        # ignore on a bug -> missed the issue (bad, but not catastrophic)
        if given == "ignore" and correct == "flag_bug":
            return 0.30, (
                "Incorrect -- you ignored a real bug. "
                + task.feedback_on_wrong
            )

        # ignore on safe code -> cautious but acceptable
        if given == "ignore" and correct == "approve":
            return 0.50, (
                "Acceptable -- you were cautious, but this diff is safe to approve. "
                + task.feedback_on_wrong
            )

        # flag_bug on safe code -> false positive (wastes reviewer time)
        if given == "flag_bug" and correct == "approve":
            return 0.15, (
                "Incorrect -- this diff is safe; flagging it is a false positive. "
                + task.feedback_on_wrong
            )

        # approve on a bug -> worst outcome (ships a vulnerability)
        if given == "approve" and correct == "flag_bug":
            return 0.10, (
                "Incorrect -- you approved a buggy/vulnerable diff. "
                + task.feedback_on_wrong
            )

        # Fallback
        return 0.10, task.feedback_on_wrong

    # ──────────────────────────────────────────────────────────────
    # state property (required by OpenEnv)
    # ──────────────────────────────────────────────────────────────
    @property
    def state(self) -> State:
        return self._state