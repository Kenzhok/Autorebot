---
title: Code Review AI Environment
emoji: 🔍
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
base_path: /web/
tags:
  - openenv
  - code-review
  - security
  - reinforcement-learning
---

# Code Review AI Environment

An **OpenEnv**-compatible reinforcement learning environment where an AI agent acts as a senior code reviewer. The agent reads code diffs and decides whether to `flag_bug`, `approve`, or `ignore` them — receiving rewards based on correctness, explanation quality, and severity classification accuracy.

Built for the **Meta × Scaler OpenEnv AI Hackathon**.

---

## Environment Overview

| Property | Value |
|---|---|
| Action Space | Discrete: `flag_bug` · `approve` · `ignore` |
| Observation | Code diff + context flags + step feedback |
| Reward Range | `0.10` to `0.90` (8-level partial credit) |
| Difficulties | `easy` · `medium` · `hard` · `all` |
| Episode Length | Up to 15 steps |
| Task Pool | 21 unique scenarios (5 easy, 5 medium, **11 hard**) |
| Per-episode | 5 tasks sampled per difficulty (seed-reproducible) |

---

## Action Space

```python
class CodeReviewAction(Action):
    action_type: str            # "flag_bug" | "approve" | "ignore"
    severity: Optional[str]     # "critical" | "medium" | "low" — affects reward
    comment: str                # Explanation — required for full marks on hard tasks
```

---

## Observation Space

```python
class CodeReviewObservation(Observation):
    current_diff: Diff       # The code diff to review
    steps_remaining: int     # Steps left in this episode
    step: int                # Current step number
    total_tasks: int         # Total tasks in this episode
    feedback: str            # Human-readable feedback on the last action
    task_difficulty: str     # "easy" | "medium" | "hard"
    reward: float            # Reward received for the last action
    done: bool               # Whether the episode is complete
    metadata: dict           # Debug info (task_id, episode_id, etc.)
```

The `current_diff` contains:
```python
class Diff(BaseModel):
    id: str               # Unique diff identifier
    diff_text: str        # The raw code change as a diff string
    risk_hints: List[str] # Risk patterns detected (e.g. "sql_concat", "ssrf")
    has_tests: bool       # Whether the diff includes tests
    touches_auth: bool    # Whether the diff touches auth/security logic
```

---

## Reward Function (8-Level Partial Credit)

The reward function rewards both **correctness** and **explanation quality**, and uses
severity classification as an additional signal.

### Easy / Medium tasks (`flag_bug` actions)

| Situation | Reward |
|---|---|
| Correct action + correct severity | `0.90` |
| Correct action, no severity specified | `0.83` |
| Ignored a real bug | `0.30` |
| Approved a buggy diff *(worst outcome)* | `0.10` |

### Hard tasks (`flag_bug` actions)

| Situation | Reward |
|---|---|
| Correct + comment + correct severity | `0.90` *(full marks)* |
| Correct + comment, wrong/no severity | `0.87` |
| Correct + correct severity, no comment | `0.85` |
| Correct, no comment, no severity | `0.80` *(minimum partial)* |
| Missed the bug (ignored) | `0.30` |
| Approved a critical vulnerability | `0.10` |

### Approve / Ignore tasks (all difficulties)

| Situation | Reward |
|---|---|
| Correct `approve` | `0.90` |
| Cautious `ignore` on safe code | `0.50` |
| False positive (flagged safe code) | `0.15` |

---

## Task Descriptions

### Easy (5 tasks — always all 5)

| ID | Vulnerability | Correct Action | Severity |
|---|---|---|---|
| e1 | Hardcoded password in source code | `flag_bug` | `critical` |
| e2 | Division function with no zero-guard | `flag_bug` | `medium` |
| e3 | Unused imports only | `ignore` | — |
| e4 | SQL query built with f-string interpolation | `flag_bug` | `critical` |
| e5 | Safe, tested `greet()` utility function | `approve` | — |

### Medium (5 tasks — always all 5)

| ID | Vulnerability | Correct Action | Severity |
|---|---|---|---|
| m1 | User profile fetch with no auth check | `flag_bug` | `critical` |
| m2 | Password stored in plaintext | `flag_bug` | `critical` |
| m3 | Loop accessing `items[i+1]` — off-by-one | `flag_bug` | `medium` |
| m4 | Auth token written to application logs | `flag_bug` | `critical` |
| m5 | Shared counter across threads without a lock | `flag_bug` | `medium` |

### Hard (11-task pool — 5 randomly sampled per episode)

| ID | Vulnerability | Correct Action | Severity |
|---|---|---|---|
| h1 | JWT decoded with `verify_signature: False` | `flag_bug` | `critical` |
| h2 | `pickle.loads()` on untrusted user input (RCE) | `flag_bug` | `critical` |
| h3 | Regex with nested quantifiers — ReDoS | `flag_bug` | `medium` |
| h4 | HTTP request to user-controlled URL — SSRF | `flag_bug` | `critical` |
| h5 | Clean, tested order-processing function | `approve` | — |
| h6 | Secret compared with `==` instead of `hmac.compare_digest` | `flag_bug` | `medium` |
| h7 | User input used directly in `open()` path — path traversal | `flag_bug` | `critical` |
| h8 | Correct HMAC-SHA256 webhook verification (deceptive) | `approve` | — |
| h9 | Django serializer with `fields='__all__'` — mass assignment | `flag_bug` | `critical` |
| h10 | Flask redirect to user-supplied URL — open redirect | `flag_bug` | `medium` |
| h11 | Secure password-reset token using `secrets` + hash (deceptive) | `approve` | — |

> **Note:** h5, h8, h11 are intentionally deceptive-safe tasks — they test whether agents avoid over-flagging secure, well-implemented code.

---

## Graders

Each difficulty tier has an independent grader that evaluates the full episode trajectory:

```python
easy_grader(trajectory: dict = None)   -> float  # (0.01, 0.99)
medium_grader(trajectory: dict = None) -> float  # (0.01, 0.99)
hard_grader(trajectory: dict = None)   -> float  # (0.01, 0.99)
```

Grader scoring logic:
- **Base score**: mean of per-step rewards
- **Catastrophe penalty**: each approved bug reduces score significantly (`-0.18` easy, `-0.15` medium, `-0.12` hard)
- **Consistency bonus**: `+0.03` if ≥80% of steps are correct
- **Explanation bonus**: `+0.02–0.04` if ≥80% of steps hit max reward (agent gave comments on hard tasks)

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
docker build -t code-review-env:latest .
docker run -p 7860:7860 code-review-env:latest
```

Then run the inference agent:

```bash
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export HF_TOKEN=hf_your_token_here
export ENV_URL=http://localhost:7860

python inference.py --difficulty all
```

### Option 2: Local Development

```bash
pip install uv
uv sync

# Start the server
uvicorn server.app:app --reload --port 7860

# Run LLM inference agent
python inference.py --difficulty all

# Run rule-based demo
python run_demo.py
```

### Option 3: Connect to Hugging Face Space

```python
from code_review_env import CodeReviewAction, CodeReviewEnv

with CodeReviewEnv(base_url="https://kenzhok-code-review-env.hf.space").sync() as env:
    result = env.reset(difficulty="hard", seed=42)
    print(result.observation.current_diff.diff_text)

    action = CodeReviewAction(
        action_type="flag_bug",
        severity="critical",
        comment="JWT signature verification is disabled — token forgery is trivial.",
    )
    result = env.step(action)
    print(result.observation.feedback)   # "Correct! Disabling JWT..."
    print(result.reward)                 # 0.90
```

---

## Project Structure

```
code_review_env/
├── __init__.py                          # Package exports
├── agent.py                             # Rule-based + LLM agent
├── client.py                            # OpenEnv HTTP/WebSocket client
├── inference.py                         # [JUDGE] LLM inference script
├── models.py                            # Pydantic Action / Observation / Diff models
├── openenv.yaml                         # OpenEnv manifest (tasks + graders)
├── pyproject.toml                       # Package config & dependencies
├── run_demo.py                          # Local demo runner (rule-based agent)
├── server/
│   ├── app.py                           # FastAPI server (HTTP + WebSocket)
│   ├── code_review_env_environment.py   # Core RL environment logic
│   ├── graders.py                       # Weighted grader functions (easy/medium/hard)
│   ├── requirements.txt                 # Server runtime dependencies
│   └── tasks.py                         # 21-task pool with seed-based sampling
└── tests/
    └── test_env.py                      # 38 unit tests (pytest)
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reset` | Reset environment, start new episode |
| `POST` | `/step` | Submit action, receive observation + reward |
| `GET` | `/state` | Get current episode state |
| `GET` | `/schema` | Get action/observation JSON schemas |
| `GET` | `/tasks` | List of supported environment tasks and grader mappings |
| `WS` | `/ws` | WebSocket for persistent sessions |
| `GET` | `/docs` | Swagger API documentation |

---

## Testing

```bash
# Run unit tests
pip install pytest
pytest tests/test_env.py -v

# 38 tests covering:
# - Environment init and super().__init__() wiring
# - reset() with seed reproducibility
# - All 8 reward ladder levels
# - Episode boundaries
# - Task pool sampling (hard tier: 11 tasks, 5 per episode)
# - Grader weighted scoring and catastrophe penalties
```

---

## Pre-Submission Validation

```bash
# Validate OpenEnv spec compliance
openenv validate

# Run against deployed Space
./validate-submission.sh https://kenzhok-code-review-env.hf.space
```

---

## Required Environment Variables

| Variable | Description |
|---|---|
| `API_BASE_URL` | OpenAI-compatible API endpoint for LLM calls |
| `MODEL_NAME` | Model identifier (e.g. `meta-llama/Llama-3.3-70B-Instruct`) |
| `HF_TOKEN` | Hugging Face / API key |
| `ENV_URL` | *(Optional)* Environment server URL — defaults to HF Space |
