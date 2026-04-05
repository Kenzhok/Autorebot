---
title: Code Review AI Environment
emoji: 🔍
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
app_port: 7860
base_path: /web
tags:
  - openenv
  - code-review
  - security
  - reinforcement-learning
---

# 🔍 Code Review AI Environment

An **OpenEnv**-compatible reinforcement learning environment where an AI agent acts as a senior code reviewer. The agent reads code diffs and decides whether to `flag_bug`, `approve`, or `ignore` them — receiving rewards based on correctness and explanation quality.

Built for the **Meta × Scaler OpenEnv AI Hackathon**.

---

## 🏗️ Environment Overview

| Property | Value |
|---|---|
| Action Space | Discrete: `flag_bug`, `approve`, `ignore` |
| Observation | Code diff + context flags + feedback |
| Reward Range | `-0.5` to `+1.0` (partial credit) |
| Difficulties | `easy`, `medium`, `hard`, `all` |
| Episode Length | Up to 15 steps |
| Tasks Total | 15 (5 per difficulty) |

---

## 📋 Action Space

```python
class CodeReviewAction(Action):
    action_type: str   # "flag_bug" | "approve" | "ignore"
    comment: str       # Explanation — used for partial credit on hard tasks
    severity: str      # Optional: "critical" | "medium" | "low"
```

---

## 👁️ Observation Space

```python
class CodeReviewObservation(Observation):
    current_diff: Diff       # The code diff to review
    steps_remaining: int     # Steps left in this episode
    step: int                # Current step number
    total_tasks: int         # Total tasks in this episode
    feedback: str            # Human-readable feedback on the last action
    task_difficulty: str     # "easy" | "medium" | "hard"
    reward: float            # Reward from last action
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

## 🎯 Reward Function (Partial Credit)

| Situation | Reward |
|---|---|
| Correct action on easy/medium task | `+1.0` |
| Correct action on hard task **with** comment | `+1.0` |
| Correct action on hard task **without** comment | `+0.7` |
| `ignore` on a real bug | `-0.3` |
| `ignore` on safe code | `0.0` |
| `flag_bug` on safe code (false positive) | `-0.5` |
| `approve` on a buggy diff | `-0.5` |

---

## 📚 Task Descriptions

### Easy (5 tasks)
| ID | Description | Correct Action |
|---|---|---|
| e1 | Hardcoded password in source code | `flag_bug` |
| e2 | Division function with no zero-guard | `flag_bug` |
| e3 | Unused imports only | `ignore` |
| e4 | SQL query built with f-string interpolation | `flag_bug` |
| e5 | Safe, tested `greet()` utility function | `approve` |

### Medium (5 tasks)
| ID | Description | Correct Action |
|---|---|---|
| m1 | User profile fetch with no auth check | `flag_bug` |
| m2 | Password stored in plaintext | `flag_bug` |
| m3 | Loop accessing `items[i+1]` — off-by-one | `flag_bug` |
| m4 | Auth token written to application logs | `flag_bug` |
| m5 | Shared counter incremented across threads without a lock | `flag_bug` |

### Hard (5 tasks)
| ID | Description | Correct Action |
|---|---|---|
| h1 | JWT decoded with `verify_signature: False` | `flag_bug` |
| h2 | `pickle.loads()` on untrusted user input | `flag_bug` |
| h3 | Regex with nested quantifiers — ReDoS vulnerability | `flag_bug` |
| h4 | HTTP request to user-controlled URL — SSRF | `flag_bug` |
| h5 | Clean, tested order processing function | `approve` |

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Build the image
docker build -t code_review_env-env:latest .

# Run the server
docker run -p 7860:7860 code_review_env-env:latest
```

Then run the inference agent:

```bash
export API_BASE_URL=https://api-inference.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export HF_TOKEN=hf-your-token-here
export ENV_URL=http://localhost:7860

python inference.py --difficulty all
```

### Option 2: Local Development (No Docker)

```bash
# Install dependencies
pip install uv
uv sync

# Start the server
uvicorn server.app:app --reload --port 7860

# In another terminal, run the demo (rule-based agent)
python run_demo.py

# Or run the LLM inference agent
python inference.py --difficulty all
```

### Option 3: Connect to Hugging Face Space

```python
from code_review_env import CodeReviewAction, CodeReviewEnv

with CodeReviewEnv(base_url="https://YOUR-SPACE.hf.space") as env:
    result = env.reset()
    print(result.observation.current_diff.diff_text)

    action = CodeReviewAction(action_type="flag_bug", comment="SQL injection risk")
    result = env.step(action)
    print(result.observation.feedback)
    print(result.reward)
```

---

## 📊 Baseline Scores

Measured over a full `difficulty=all` episode (15 tasks):

| Agent | Total Reward | Accuracy |
|---|---|---|
| Always `flag_bug` | 10.5 / 15 | 86.7% (misses 2 approve tasks) |
| Rule-based (agent.py) | 12.5 / 15 | 93.3% |
| LLM (Llama-3.3-70B) | ~13.5 / 15 | ~90% |

---

## 📁 Project Structure

```
code_review_env/
├── __init__.py                          # Package exports
├── agent.py                             # Rule-based + LLM agent
├── client.py                            # OpenEnv HTTP/WebSocket client
├── inference.py                         # 🔴 Judge inference script (LLM agent)
├── models.py                            # Pydantic Action / Observation / Diff models
├── openenv.yaml                         # OpenEnv manifest
├── pyproject.toml                       # Package config & dependencies
├── README.md                            # This file
├── run_demo.py                          # Local demo runner (rule-based agent)
└── server/
    ├── __init__.py
    ├── app.py                           # FastAPI server (HTTP + WebSocket)
    ├── code_review_env_environment.py   # Core RL environment logic
    ├── tasks.py                         # 15-task dataset with graders
    └── requirements.txt                 # Server dependencies
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reset` | Reset the environment, start a new episode |
| `POST` | `/step` | Submit an action, receive observation + reward |
| `GET` | `/state` | Get current episode state |
| `GET` | `/schema` | Get action/observation JSON schemas |
| `WS` | `/ws` | WebSocket for persistent low-latency sessions |
| `GET` | `/web` | Interactive web UI |
| `GET` | `/docs` | Swagger API documentation |

---

## ✅ Pre-Submission Validation

```bash
# Validate OpenEnv spec compliance
openenv validate

# Run pre-submission check against your deployed space
./validate-submission.sh https://YOUR-SPACE.hf.space
```
