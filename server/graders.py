"""
graders.py — Weighted grader functions for the Code Review Environment.

Each grader receives a trajectory dict from an episode and returns a score
strictly in (0.01, 0.99) as required by the OpenEnv judge.

Per-step reward map (see code_review_env_environment.py):
  0.90 — correct action + correct severity (or approve/ignore correct)
  0.88 — correct flag_bug on easy/medium, no severity specified
  0.87 — correct hard + comment + no severity
  0.85 — correct hard + comment + wrong severity
  0.83 — correct hard + correct severity + no comment
  0.80 — correct hard + wrong severity + no comment
  0.70 — correct hard + no comment + no severity (minimum partial credit)
  0.50 — ignore on safe code (cautious but acceptable)
  0.30 — ignore on a real bug (missed the issue)
  0.15 — flag safe code as bug (false positive)
  0.10 — approve a buggy diff (worst outcome — ships a vulnerability)

Grader design philosophy:
  - Catastrophic mistakes (approving bugs) are penalised non-linearly.
  - Explanation quality is inferred from the 0.90 vs lower reward signal.
  - Consistency matters: an agent that mostly gets it right with one slip
    should score higher than one that's mediocre across the board.
"""
from typing import List


# ── Reward range constants ─────────────────────────────────────────────────────
_APPROVE_BUG   = 0.10   # approved a vulnerability — ships to prod
_FALSE_POS     = 0.15   # flagged safe code — false positive
_MISSED_BUG    = 0.30   # ignored a real bug
_CAUTIOUS      = 0.50   # ignored safe code (acceptable)
_PARTIAL_HARD  = 0.70   # correct hard task with no comment/severity
_FULL_EASY_MED = 0.88   # correct easy/medium without severity
_FULL_CORRECT  = 0.90   # perfect: correct + severity + comment (hard)


def _classify(reward: float) -> str:
    """Classify a per-step reward into a named outcome bucket."""
    if reward <= _APPROVE_BUG:
        return "approve_bug"
    if reward <= _FALSE_POS:
        return "false_positive"
    if reward <= _MISSED_BUG:
        return "missed_bug"
    if reward <= _CAUTIOUS:
        return "cautious"
    # 0.51–0.69: shouldn't occur but treat as low_partial
    if reward < _PARTIAL_HARD:
        return "low_partial"
    # 0.70–0.87: partial credit (correct but missing comment/severity)
    if reward < _FULL_EASY_MED:
        return "partial_credit"
    # 0.88+: full or near-full marks
    return "correct"


def _base_score(rewards: List[float]) -> float:
    """Simple mean, clamped."""
    if not rewards:
        return 0.5
    return sum(rewards) / len(rewards)


def _weighted_score(
    rewards: List[float],
    approve_bug_penalty: float = 0.15,
    missed_bug_penalty: float  = 0.04,
    consistency_bonus: float   = 0.03,
    explanation_bonus: float   = 0.02,
) -> float:
    """
    Compute a weighted score from a reward list.

    Args:
        rewards: Per-step rewards from the episode.
        approve_bug_penalty: Extra deduction per approved-bug step.
        missed_bug_penalty:  Extra deduction per missed-bug step.
        consistency_bonus:   Bonus when ≥80% of steps are 'correct'.
        explanation_bonus:   Bonus when ≥80% of steps hit max reward (0.90).

    Returns:
        float in (0.01, 0.99).
    """
    if not rewards:
        return 0.5

    n = len(rewards)
    classified = [_classify(r) for r in rewards]

    # Base score
    mean = _base_score(rewards)

    # Catastrophic penalty: each approved bug drags the score down hard
    approve_bugs  = classified.count("approve_bug")
    missed_bugs   = classified.count("missed_bug")
    false_pos     = classified.count("false_positive")

    penalty = (
        min(approve_bugs  * approve_bug_penalty, 0.45) +
        min(missed_bugs   * missed_bug_penalty,  0.20) +
        min(false_pos     * 0.02,                0.10)
    )

    # Consistency bonus: agent that is mostly correct
    correct_count = classified.count("correct") + classified.count("partial_credit")
    if correct_count / n >= 0.80:
        bonus = consistency_bonus
    else:
        bonus = 0.0

    # Explanation bonus: high proportion of max-reward steps (agent gave comments)
    top_count = sum(1 for r in rewards if r >= _FULL_CORRECT - 0.01)
    if top_count / n >= 0.80:
        bonus += explanation_bonus

    score = mean - penalty + bonus
    return min(max(round(score, 4), 0.01), 0.99)


# ── Public grader functions ────────────────────────────────────────────────────

def easy_grader(trajectory: dict) -> float:
    """
    Grader for easy code-review tasks.

    Easy tasks feature obvious, high-signal vulnerabilities:
      - Hardcoded credentials
      - SQL f-string injection
      - Division-by-zero without guard
      - Unused imports  (correct action: ignore)
      - Safe, tested utility function  (correct action: approve)

    A perfect agent should score 0.88–0.90 on every step.
    Approving any easy bug is treated as a serious mistake.

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _weighted_score(
        rewards,
        approve_bug_penalty=0.18,  # high: easy bugs should be obvious
        missed_bug_penalty=0.05,
        consistency_bonus=0.03,
        explanation_bonus=0.01,
    )


def medium_grader(trajectory: dict) -> float:
    """
    Grader for medium code-review tasks.

    Medium tasks require understanding of auth, data handling,
    and concurrency — not just surface pattern-matching.

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _weighted_score(
        rewards,
        approve_bug_penalty=0.15,
        missed_bug_penalty=0.05,
        consistency_bonus=0.03,
        explanation_bonus=0.01,
    )


def hard_grader(trajectory: dict) -> float:
    """
    Grader for hard code-review tasks.

    Hard tasks require deep expertise:
      - JWT signature bypass
      - Insecure pickle deserialisation (RCE)
      - ReDoS via catastrophic backtracking
      - SSRF via user-controlled URLs
      - Timing attacks, path traversal
      - Deceptive-but-safe code (must approve correctly)

    The explanation_bonus is larger here because hard tasks explicitly
    reward agents that justify their decisions (0.90 vs ≤0.87).

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _weighted_score(
        rewards,
        approve_bug_penalty=0.12,  # slightly lower: hard tasks are genuinely tricky
        missed_bug_penalty=0.04,
        consistency_bonus=0.02,
        explanation_bonus=0.04,   # larger bonus: rewards agents that explain their reasoning
    )
