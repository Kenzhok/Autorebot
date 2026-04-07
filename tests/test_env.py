"""
tests/test_env.py — Unit tests for the Code Review Environment.

Tests cover:
  - Environment initialisation and superclass wiring
  - reset() with various difficulty/seed combinations
  - step() reward ladder correctness
  - Grader weighted-penalty scoring
  - Full episode flow
"""
import sys
import os
import pytest

# Support running via: pytest tests/test_env.py  (from project root)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from code_review_env.server.code_review_env_environment import CodeReviewEnvironment
    from code_review_env.models import CodeReviewAction
    from code_review_env.server.graders import easy_grader, medium_grader, hard_grader
    from code_review_env.server.tasks import get_tasks
except ImportError:
    from server.code_review_env_environment import CodeReviewEnvironment
    from models import CodeReviewAction
    from server.graders import easy_grader, medium_grader, hard_grader
    from server.tasks import get_tasks


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def env():
    """Fresh environment instance for each test."""
    return CodeReviewEnvironment()


@pytest.fixture
def easy_env(env):
    """Environment reset to easy difficulty."""
    env.reset(difficulty="easy")
    return env


@pytest.fixture
def hard_env(env):
    """Environment reset to hard difficulty."""
    env.reset(difficulty="hard")
    return env


# ── Initialisation ─────────────────────────────────────────────────────────────

class TestInit:
    def test_super_init_called(self, env):
        """super().__init__() must initialise transform and rubric."""
        assert hasattr(env, "transform"), "self.transform not set — super().__init__() missing"
        assert hasattr(env, "rubric"),    "self.rubric not set — super().__init__() missing"

    def test_concurrent_sessions_flag(self):
        assert CodeReviewEnvironment.SUPPORTS_CONCURRENT_SESSIONS is True

    def test_initial_state(self, env):
        assert env.tasks == []
        assert env.current_index == 0
        assert env.steps_used == 0


# ── reset() ────────────────────────────────────────────────────────────────────

class TestReset:
    def test_reset_returns_observation(self, env):
        obs = env.reset()
        assert obs is not None
        assert obs.done is False
        assert obs.reward == 0.0
        assert obs.current_diff is not None

    def test_reset_loads_five_tasks(self, env):
        env.reset(difficulty="easy")
        assert len(env.tasks) == 5

    def test_reset_hard_loads_five_from_pool(self, env):
        """Hard pool has 8 tasks; reset must sample exactly 5."""
        env.reset(difficulty="hard")
        assert len(env.tasks) == 5

    def test_reset_all_loads_fifteen_tasks(self, env):
        env.reset(difficulty="all")
        assert len(env.tasks) == 15

    def test_seed_produces_different_orders(self, env):
        env.reset(difficulty="easy", seed=1)
        order_a = [t.id for t in env.tasks]
        env.reset(difficulty="easy", seed=99)
        order_b = [t.id for t in env.tasks]
        assert order_a != order_b, "Different seeds must produce different task orders"

    def test_same_seed_is_reproducible(self, env):
        env.reset(difficulty="easy", seed=42)
        order_a = [t.id for t in env.tasks]
        env.reset(difficulty="easy", seed=42)
        order_b = [t.id for t in env.tasks]
        assert order_a == order_b, "Same seed must always produce same order"

    def test_reset_accepts_framework_args(self, env):
        """Framework passes seed and episode_id — must not TypeError."""
        obs = env.reset(seed=7, episode_id="test-ep-001")
        assert obs is not None

    def test_reset_clears_previous_state(self, env):
        env.reset(difficulty="easy")
        env.step(CodeReviewAction(action_type="flag_bug"))
        assert env.steps_used == 1
        env.reset(difficulty="easy")
        assert env.steps_used == 0
        assert env.current_index == 0


# ── step() reward ladder ───────────────────────────────────────────────────────

class TestStepRewards:
    def _first_flag_task(self, env):
        """Return (env, task) where current task expects flag_bug."""
        for i, task in enumerate(env.tasks):
            if task.correct_action == "flag_bug":
                env.current_index = i
                return task
        pytest.skip("No flag_bug task found at this difficulty")

    def _first_approve_task(self, env):
        for i, task in enumerate(env.tasks):
            if task.correct_action == "approve":
                env.current_index = i
                return task
        pytest.skip("No approve task found at this difficulty")

    # ── Easy / medium: severity bonus ─────────────────────────────────────────

    def test_easy_correct_with_severity_gives_090(self, easy_env):
        task = self._first_flag_task(easy_env)
        action = CodeReviewAction(
            action_type="flag_bug",
            severity=task.correct_severity,
        )
        obs = easy_env.step(action)
        assert obs.reward == 0.90

    def test_easy_correct_without_severity_gives_083(self, easy_env):
        self._first_flag_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="flag_bug", severity=None))
        assert obs.reward == 0.83

    def test_approve_correct_gives_090(self, easy_env):
        self._first_approve_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="approve"))
        assert obs.reward == 0.90

    # ── Hard tier: comment + severity ─────────────────────────────────────────

    def test_hard_correct_with_comment_and_severity_gives_090(self, hard_env):
        task = self._first_flag_task(hard_env)
        obs = hard_env.step(CodeReviewAction(
            action_type="flag_bug",
            severity=task.correct_severity,
            comment="JWT signature verification is disabled, enabling token forgery.",
        ))
        assert obs.reward == 0.90

    def test_hard_correct_with_comment_no_severity_gives_087(self, hard_env):
        self._first_flag_task(hard_env)
        obs = hard_env.step(CodeReviewAction(
            action_type="flag_bug",
            severity=None,
            comment="This disables JWT verification.",
        ))
        assert obs.reward == 0.87

    def test_hard_correct_no_comment_no_severity_gives_080(self, hard_env):
        self._first_flag_task(hard_env)
        obs = hard_env.step(CodeReviewAction(action_type="flag_bug"))
        assert obs.reward == 0.80

    # ── Wrong actions ─────────────────────────────────────────────────────────

    def test_missed_bug_gives_030(self, easy_env):
        self._first_flag_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="ignore"))
        assert obs.reward == 0.30

    def test_approve_bug_gives_010(self, easy_env):
        self._first_flag_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="approve"))
        assert obs.reward == 0.10

    def test_false_positive_gives_015(self, easy_env):
        self._first_approve_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="flag_bug"))
        assert obs.reward == 0.15

    def test_cautious_ignore_gives_050(self, easy_env):
        self._first_approve_task(easy_env)
        obs = easy_env.step(CodeReviewAction(action_type="ignore"))
        assert obs.reward == 0.50

    # ── Episode boundaries ────────────────────────────────────────────────────

    def test_done_after_all_tasks(self, easy_env):
        for _ in range(5):
            obs = easy_env.step(CodeReviewAction(action_type="flag_bug"))
        assert obs.done is True

    def test_all_rewards_in_valid_range(self, easy_env):
        for _ in range(5):
            obs = easy_env.step(CodeReviewAction(action_type="flag_bug"))
            assert 0.01 <= obs.reward <= 0.99, f"Reward {obs.reward} out of range"


# ── Full episode ───────────────────────────────────────────────────────────────

class TestFullEpisode:
    def test_full_easy_episode_completes(self, env):
        obs = env.reset(difficulty="easy", seed=42)
        rewards = []
        steps = 0
        while not obs.done:
            obs = env.step(CodeReviewAction(
                action_type=env.tasks[max(0, env.current_index - 1)].correct_action
                if steps > 0 else "flag_bug"
            ))
            rewards.append(obs.reward)
            steps += 1
            if steps > 20:
                pytest.fail("Episode did not terminate")
        assert len(rewards) == 5
        assert obs.done is True

    def test_state_property_returns_state(self, env):
        env.reset()
        state = env.state
        assert state is not None
        assert hasattr(state, "episode_id")
        assert hasattr(state, "step_count")


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TestTaskPool:
    def test_easy_pool_size(self):
        tasks = get_tasks("easy")
        assert len(tasks) == 5

    def test_medium_pool_size(self):
        tasks = get_tasks("medium")
        assert len(tasks) == 5

    def test_hard_pool_size(self):
        """Hard pool has 8 tasks, get_tasks returns 5 by default."""
        tasks = get_tasks("hard")
        assert len(tasks) == 5

    def test_hard_full_pool_size(self):
        """Hard pool has 8 tasks accessible via n=8."""
        tasks = get_tasks("hard", n=8)
        assert len(tasks) == 8

    def test_all_tasks_have_correct_severity(self):
        for difficulty in ("easy", "medium", "hard"):
            for task in get_tasks(difficulty, n=99):
                # All flag_bug tasks must have a severity defined
                if task.correct_action == "flag_bug":
                    assert task.correct_severity in ("critical", "medium", "low"), \
                        f"Task {task.id}: flag_bug task missing correct_severity"

    def test_all_tasks_have_feedback(self):
        for difficulty in ("easy", "medium", "hard"):
            for task in get_tasks(difficulty, n=99):
                assert task.feedback_on_correct, f"Task {task.id}: missing feedback_on_correct"
                assert task.feedback_on_wrong,   f"Task {task.id}: missing feedback_on_wrong"

    def test_legacy_dict_api(self):
        """get_tasks() with no args returns full dict (backward compat)."""
        result = get_tasks()
        assert isinstance(result, dict)
        assert "easy" in result
        assert "medium" in result
        assert "hard" in result


# ── Graders ───────────────────────────────────────────────────────────────────

class TestGraders:
    def test_graders_return_valid_range(self):
        t = {"rewards": [0.90, 0.83, 0.30, 0.90, 0.90]}
        for grader in (easy_grader, medium_grader, hard_grader):
            score = grader(t)
            assert 0.01 <= score <= 0.99, f"{grader.__name__} returned {score}"

    def test_empty_trajectory_returns_neutral(self):
        for grader in (easy_grader, medium_grader, hard_grader):
            assert grader({}) == 0.5
            assert grader({"rewards": []}) == 0.5

    def test_catastrophe_penalty_applied(self):
        """An agent that approves bugs must score significantly lower."""
        good = {"rewards": [0.90, 0.90, 0.90, 0.90, 0.90]}
        bad  = {"rewards": [0.10, 0.10, 0.10, 0.10, 0.10]}
        assert easy_grader(good) > easy_grader(bad)
        assert medium_grader(good) > medium_grader(bad)
        assert hard_grader(good) > hard_grader(bad)

    def test_consistent_good_agent_gets_bonus(self):
        """Agent correct on ≥80% of steps gets consistency bonus."""
        mostly_correct   = {"rewards": [0.90, 0.90, 0.90, 0.90, 0.30]}
        inconsistent     = {"rewards": [0.90, 0.10, 0.90, 0.10, 0.90]}
        assert easy_grader(mostly_correct) > easy_grader(inconsistent)

    def test_hard_grader_rewards_explanation(self):
        """Hard grader gives extra bonus when most steps hit max reward (0.90)."""
        with_explanation    = {"rewards": [0.90, 0.90, 0.90, 0.90, 0.90]}
        without_explanation = {"rewards": [0.80, 0.80, 0.80, 0.80, 0.80]}
        assert hard_grader(with_explanation) > hard_grader(without_explanation)

    def test_grader_single_step(self):
        """Single-step episode must still return a valid score."""
        for grader in (easy_grader, medium_grader, hard_grader):
            score = grader({"rewards": [0.90]})
            assert 0.01 <= score <= 0.99
