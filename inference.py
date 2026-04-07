"""
inference.py -- Code Review AI Agent (Hackathon Submission)

Runs a full episode against the CodeReviewEnv environment server using an LLM
to decide code review actions. Prints structured logs consumed by the judge.

Required environment variables:
    API_BASE_URL  -- OpenAI-compatible API base URL
    MODEL_NAME    -- Model identifier (e.g. "meta-llama/Llama-3.3-70B-Instruct")
    HF_TOKEN      -- Hugging Face / API key

Optional environment variables:
    ENV_URL       -- Environment server URL (defaults to deployed HF Space)

Usage:
    python inference.py
    python inference.py --difficulty all
    ENV_URL=http://localhost:8000 python inference.py --difficulty easy

STDOUT FORMAT (machine-parsed by judge -- do not change):
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import argparse
import os
import sys
from typing import List, Optional

from openai import OpenAI

# ── Import the environment client ──────────────────────────────────────────────
try:
    from code_review_env import CodeReviewAction, CodeReviewEnv
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from code_review_env.client import CodeReviewEnv
    from code_review_env.models import CodeReviewAction


# ── Constants ──────────────────────────────────────────────────────────────────
ENV_URL      = os.environ.get("ENV_URL", "https://kenzhok-code-review-env.hf.space")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")  # active default
MODEL_NAME   = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")   # active default
HF_TOKEN     = os.environ.get("HF_TOKEN")  # NO default — must be set explicitly

BENCHMARK    = "code_review_env"
VALID_ACTIONS = {"flag_bug", "approve", "ignore"}

# Reward range per step in this environment: (0.10, 0.90)
# Since rewards are already normalised to a (0,1) sub-range we can use the
# mean directly.  We still clamp with an epsilon buffer so the final score
# is strictly between 0 and 1 (judge requirement: no 0.0 or 1.0).
REWARD_MIN = 0.10   # worst possible per step  (approve a bug)
REWARD_MAX = 0.90   # best possible per step   (correct action)


# ── Mandatory logging helpers (judge-parsed format) ───────────────────────────
def log_start(task: str, env_name: str, model: str) -> None:
    """[START] line — emitted exactly once at episode begin."""
    print(f"[START] task={task} env={env_name} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool,
             error: Optional[str] = None) -> None:
    """[STEP] line — emitted immediately after each env.step() returns."""
    error_val = error if error else "null"
    done_val  = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """[END] line — always emitted (even on exception) via finally block."""
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ── LLM setup ─────────────────────────────────────────────────────────────────
def get_llm_client() -> OpenAI:
    if not HF_TOKEN:
        raise EnvironmentError(
            "HF_TOKEN environment variable is not set.\n"
            "Example: set HF_TOKEN=hf_your_token_here"
        )
    return OpenAI(
        base_url=API_BASE_URL,
        api_key=HF_TOKEN,
    )


# ── Prompt builder ─────────────────────────────────────────────────────────────
def build_prompt(obs) -> str:
    diff = obs.current_diff
    return f"""You are a senior software engineer performing a code review.

Analyze the following code diff and decide ONE action:
- flag_bug  -> the diff contains a bug, vulnerability, or serious issue
- approve   -> the diff is safe and correct, approve it
- ignore    -> the diff is a minor style/cosmetic issue, not worth flagging

Code Diff:
{diff.diff_text}

Context:
- touches_auth: {diff.touches_auth}  (does it touch security/auth code?)
- has_tests:    {diff.has_tests}     (are tests included?)
- risk_hints:   {diff.risk_hints}    (known risk patterns detected)

Rules:
- If security or authentication logic is changed without tests -> flag_bug
- If there is SQL string concatenation / f-string interpolation -> flag_bug
- If credentials or tokens are hardcoded -> flag_bug
- If the diff is clearly harmless and well-tested -> approve
- If it is only a style issue (unused imports, formatting) -> ignore

Also provide a brief one-sentence explanation of your decision.

Respond in this EXACT format (two lines only):
ACTION: <flag_bug|approve|ignore>
COMMENT: <one sentence explanation>"""


# ── LLM call ──────────────────────────────────────────────────────────────────
def call_llm(client: OpenAI, prompt: str) -> tuple:
    """
    Call the LLM and parse action + comment from response.
    Returns (action_type, comment). Falls back to 'flag_bug' on any error.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[DEBUG] LLM call failed: {e}", file=sys.stderr, flush=True)
        return "flag_bug", "LLM call failed -- defaulting to flag_bug (safe choice)."

    action_type = "flag_bug"  # safe default
    comment = ""

    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            candidate = line.split(":", 1)[1].strip().lower()
            if candidate in VALID_ACTIONS:
                action_type = candidate
        elif line.upper().startswith("COMMENT:"):
            comment = line.split(":", 1)[1].strip()

    return action_type, comment


# ── Score computation ─────────────────────────────────────────────────────────
def compute_score(rewards: List[float]) -> float:
    """
    Return the mean per-step reward, clamped strictly to (0.01, 0.99).

    Per-step rewards are already in the (0.10, 0.90) sub-range so the mean
    is naturally within (0, 1).  The epsilon clamp is a safety net that
    guarantees the judge's invariant: score is never exactly 0.0 or 1.0.
    """
    if not rewards:
        return 0.50   # neutral default — no steps taken
    mean_reward = sum(rewards) / len(rewards)
    return min(max(round(mean_reward, 4), 0.01), 0.99)


# ── Main episode loop ──────────────────────────────────────────────────────────
def run_episode(difficulty: str = "all") -> None:
    llm_client   = get_llm_client()
    task_name    = f"code_review_{difficulty}"
    rewards: List[float] = []
    steps_taken  = 0
    score        = 0.0
    success      = False

    with CodeReviewEnv(base_url=ENV_URL).sync() as env:
        log_start(task=task_name, env_name=BENCHMARK, model=MODEL_NAME)

        try:
            obs_result = env.reset(difficulty=difficulty)
            obs        = obs_result.observation

            while not obs.done:
                steps_taken += 1
                prompt = build_prompt(obs)
                action_type, comment = call_llm(llm_client, prompt)

                action = CodeReviewAction(
                    action_type=action_type,
                    comment=comment,
                )

                error: Optional[str] = None
                try:
                    step_result = env.step(action)
                    obs         = step_result.observation
                    reward      = step_result.reward or 0.0
                except Exception as e:
                    reward = 0.0
                    error  = str(e)
                    rewards.append(reward)
                    log_step(step=steps_taken, action=action_type, reward=reward, done=True, error=error)
                    break  # logged, now exit loop

                rewards.append(reward)
                log_step(
                    step=steps_taken,
                    action=action_type,
                    reward=reward,
                    done=obs.done,
                    error=error,
                )

            score   = compute_score(rewards)
            success = score > 0.333  # above random-guess baseline

        except Exception as outer_exc:
            # Catch any error in reset() or the loop setup
            print(f"[DEBUG] Episode error: {outer_exc}", file=sys.stderr, flush=True)

        finally:
            # [END] MUST always be emitted — even on exception
            log_end(
                success=success,
                steps=steps_taken,
                score=score,
                rewards=rewards,
            )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Code Review AI Agent -- Hackathon inference script"
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default="all",
        choices=["easy", "medium", "hard", "all"],
        help="Difficulty level of tasks to run (default: all)",
    )
    args = parser.parse_args()
    run_episode(difficulty=args.difficulty)
