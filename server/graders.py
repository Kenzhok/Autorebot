"""
graders.py — Grader functions for the Code Review Environment.

Each grader receives a trajectory dict (containing step rewards) from an
episode and returns a normalised score **strictly between 0 and 1**
(never exactly 0.0 or 1.0), as required by the OpenEnv judge.

Per-step reward mapping (see code_review_env_environment.py):
  0.90 — correct action on easy/medium task
  0.70 — correct on hard task but no explanatory comment
  0.90 — correct on hard task with comment
  0.50 — ignore on safe code  (cautious but acceptable)
  0.30 — ignore on a real bug  (missed the issue)
  0.15 — flag safe code        (false positive)
  0.10 — approve a buggy diff  (worst outcome)

All values are in (0.1, 0.9] so the mean is always strictly in (0, 1).
An extra epsilon clamp to [0.01, 0.99] is applied for safety.
"""
from typing import List


# ── internal helper ────────────────────────────────────────────────────────────
def _mean_reward_score(rewards: List[float]) -> float:
    """
    Return the mean of *rewards* clamped to (0.01, 0.99).

    The clamping ensures the score is always **strictly** between 0 and 1,
    satisfying the judge's Phase-2 validation gate.
    """
    if not rewards:
        return 0.5          # neutral default — episode produced no steps
    mean = sum(rewards) / len(rewards)
    return min(max(round(mean, 4), 0.01), 0.99)


# ── public grader functions ────────────────────────────────────────────────────

def easy_grader(trajectory: dict) -> float:
    """
    Grader for **easy** code-review tasks.

    Evaluates agent performance on obvious vulnerabilities:
      - Hardcoded credentials
      - SQL f-string injection
      - Division-by-zero without guard
      - Unused imports (style, should ignore)
      - Safe, well-tested utility functions (should approve)

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _mean_reward_score(rewards)


def medium_grader(trajectory: dict) -> float:
    """
    Grader for **medium** code-review tasks.

    Evaluates detection of moderately subtle issues:
      - Missing authentication before data access
      - Plaintext password storage
      - Off-by-one index error
      - Sensitive token written to logs
      - Unsynchronised shared counter (race condition)

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _mean_reward_score(rewards)


def hard_grader(trajectory: dict) -> float:
    """
    Grader for **hard** code-review tasks.

    Evaluates deep security expertise:
      - JWT signature-verification bypass
      - Insecure pickle deserialisation (RCE)
      - ReDoS via catastrophic backtracking regex
      - Server-Side Request Forgery (SSRF)
      - Complex business logic (approve when truly safe)

    Hard tasks also reward a quality explanatory comment — agents that
    supply ``comment`` receive a higher per-step reward (0.90 vs 0.70).

    Args:
        trajectory: dict with at least a ``rewards`` key (list[float]).

    Returns:
        float strictly in (0.01, 0.99).
    """
    rewards: List[float] = trajectory.get("rewards", [])
    return _mean_reward_score(rewards)
