from uuid import uuid4
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
        self._seed = None
        self.difficulty = "easy"
        self.tasks = []
        self.current_index = 0
        self.steps_used = 0
        self.steps_max = 15  # enough headroom for all-difficulty (15 tasks)

    # ──────────────────────────────────────────────────────────────
    # reset
    # ──────────────────────────────────────────────────────────────
    def reset(self, seed=None, episode_id=None, difficulty: str = "easy", **kwargs) -> CodeReviewObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count += 1
        self._seed = seed
        self.difficulty = difficulty

        # Use seed for reproducible task shuffling (Phase 2 variance check)
        int_seed = int(seed) if seed is not None else None

        if difficulty == "all":
            self.tasks = (
                get_tasks("easy",   seed=int_seed, n=5)
                + get_tasks("medium", seed=int_seed, n=5)
                + get_tasks("hard",   seed=int_seed, n=5)
            )
        else:
            self.tasks = get_tasks(difficulty, seed=int_seed, n=5)

        self.current_index = 0
        self.steps_used = 0

        return self._get_observation(reward=0.0, done=False, feedback="Episode started. Review the diff carefully.")

    # ──────────────────────────────────────────────────────────────
    # step
    # ──────────────────────────────────────────────────────────────
    def step(self, action: CodeReviewAction) -> CodeReviewObservation:
        self._state.step_count += 1

        # Safety: re-load tasks if empty (e.g. after unexpected deserialization)
        if not self.tasks:
            self.tasks = get_tasks(self.difficulty, seed=self._seed, n=5)

        if self.current_index >= len(self.tasks):
            return self._get_observation(reward=0.0, done=True, feedback="Episode already complete.")

        current_task = self.tasks[self.current_index]

        # Calculate partial-credit reward (incorporates severity signal)
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
            self.tasks = get_tasks(self.difficulty, seed=self._seed, n=5)

        total_tasks = len(self.tasks)

        if self.current_index >= len(self.tasks):
            task = self.tasks[-1]
            steps_remaining = 0
        else:
            task = self.tasks[self.current_index]
            steps_remaining = max(0, self.steps_max - self.steps_used)

        return CodeReviewObservation(
            current_diff=task.diff,
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
    # _calculate_reward
    # ──────────────────────────────────────────────────────────────
    # Reward ladder (strictly in (0.10, 0.90)):
    #
    #  flag_bug tasks (bugs that must be caught):
    #   0.90  correct + correct severity (+ comment on hard)
    #   0.87  correct + comment, no/wrong severity       [hard only]
    #   0.85  correct + correct severity, no comment     [hard only]
    #   0.83  correct flag_bug easy/medium + no severity
    #   0.80  correct flag_bug hard + no comment + no severity
    #   0.30  ignore a real bug  (missed it)
    #   0.10  approve a buggy diff  (worst outcome)
    #
    #  approve tasks (safe code that must pass):
    #   0.90  correct approve
    #   0.50  ignore safe code  (cautious but acceptable)
    #   0.15  flag_bug on safe code  (false positive)
    #
    #  ignore tasks (style issues, not worth flagging):
    #   0.90  correct ignore
    # ──────────────────────────────────────────────────────────────
    def _calculate_reward(self, action: CodeReviewAction, task) -> tuple:
        correct   = task.correct_action
        given     = action.action_type
        difficulty = task.difficulty
        has_comment  = bool(action.comment and action.comment.strip())
        has_severity = bool(action.severity)

        # Does the agent's severity classification match the task's expected severity?
        expected_sev = task.correct_severity
        severity_correct = (
            expected_sev is None           # task has no expected severity → any is fine
            or action.severity == expected_sev
        )

        # ── Correct action ─────────────────────────────────────────
        if given == correct:

            # All non-flag_bug correct actions: full marks (no severity signal)
            if correct != "flag_bug":
                return 0.90, task.feedback_on_correct

            # --- Correct flag_bug: severity + comment affect the score ---

            if difficulty == "hard":
                # Hard tasks reward both explanation and correct severity classification
                if has_comment and severity_correct:
                    return 0.90, task.feedback_on_correct
                if has_comment and not severity_correct:
                    tip = " (Tip: also specify the correct severity level.)"
                    return 0.87, task.feedback_on_correct + tip
                if not has_comment and severity_correct and has_severity:
                    tip = " (Tip: add a comment explaining the vulnerability for full marks.)"
                    return 0.85, task.feedback_on_correct + tip
                # No comment, wrong/missing severity
                tip = " (Tip: add a comment and specify severity for full marks.)"
                return 0.80, task.feedback_on_correct + tip

            else:
                # Easy / medium: severity is a bonus signal
                if severity_correct and has_severity:
                    return 0.90, task.feedback_on_correct
                # No severity or wrong → small reduction (severity info is helpful)
                tip = " (Tip: specify the severity level for more precise feedback.)"
                return 0.83, task.feedback_on_correct + tip

        # ── Wrong actions — nuanced penalties ──────────────────────

        # ignore on a bug → missed the issue (bad but not catastrophic)
        if given == "ignore" and correct == "flag_bug":
            return 0.30, "Incorrect — you ignored a real bug. " + task.feedback_on_wrong

        # ignore on safe code → cautious but acceptable
        if given == "ignore" and correct == "approve":
            return 0.50, (
                "Acceptable — you were cautious, but this diff is safe to approve. "
                + task.feedback_on_wrong
            )

        # flag_bug on safe code → false positive (wastes reviewer time)
        if given == "flag_bug" and correct == "approve":
            return 0.15, (
                "Incorrect — this diff is safe; flagging it is a false positive. "
                + task.feedback_on_wrong
            )

        # approve on a bug → worst outcome (ships a vulnerability)
        if given == "approve" and correct == "flag_bug":
            return 0.10, (
                "Incorrect — you approved a buggy/vulnerable diff. "
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