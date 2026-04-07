from typing import Dict, List, Optional
from pydantic import BaseModel
import importlib
import random

# Always resolve Diff from the same module object to avoid Pydantic
# "two different classes" validation errors when sys.path varies.
def _import_diff():
    for mod_name in ("code_review_env.models", "models"):
        try:
            mod = importlib.import_module(mod_name)
            return mod.Diff
        except (ImportError, AttributeError):
            continue
    raise ImportError("Cannot import Diff from code_review_env.models or models")

Diff = _import_diff()


class Task(BaseModel):
    id: str
    diff: Diff
    correct_action: str          # flag_bug | approve | ignore
    correct_severity: Optional[str] = None  # critical | medium | low | None
    difficulty: str
    feedback_on_correct: str = ""
    feedback_on_wrong: str = ""


def _build_all_tasks() -> Dict[str, List[Task]]:
    """Build and return the complete task pool for all difficulty tiers."""
    return {

        # ── EASY (5 tasks) ─────────────────────────────────────────────────
        # Obvious, high-signal vulnerabilities an agent should always spot.
        "easy": [
            Task(
                id="e1",
                diff=Diff(
                    id="e1",
                    diff_text=(
                        "-password = 'admin123'\n"
                        "+password = 'admin123'  # TODO: change before prod"
                    ),
                    risk_hints=["hardcoded_secret"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="easy",
                feedback_on_correct="Correct! Hardcoded credentials are a critical security risk.",
                feedback_on_wrong="Wrong. Hardcoded passwords must always be flagged.",
            ),
            Task(
                id="e2",
                diff=Diff(
                    id="e2",
                    diff_text=(
                        "+def divide(a, b):\n"
                        "+    return a / b"
                    ),
                    risk_hints=["division_by_zero"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="easy",
                feedback_on_correct="Correct! No zero-check before division -- will raise ZeroDivisionError.",
                feedback_on_wrong="Wrong. Division without a zero-guard is a bug.",
            ),
            Task(
                id="e3",
                diff=Diff(
                    id="e3",
                    diff_text=(
                        "+import os\n"
                        "+import sys\n"
                        "+import json  # never used\n"
                        "+import re    # never used\n"
                        "+\n"
                        "+def main():\n"
                        "+    print(os.getcwd())"
                    ),
                    risk_hints=["unused_imports"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="ignore",
                correct_severity=None,
                difficulty="easy",
                feedback_on_correct="Correct! Unused imports are a style issue, not a bug worth flagging in review.",
                feedback_on_wrong="Wrong. Unused imports are a linting concern -- not a functional bug.",
            ),
            Task(
                id="e4",
                diff=Diff(
                    id="e4",
                    diff_text=(
                        "+def get_username(user_id):\n"
                        "+    return db.query(f'SELECT name FROM users WHERE id={user_id}')"
                    ),
                    risk_hints=["sql_concat"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="easy",
                feedback_on_correct="Correct! String-formatted SQL is a classic SQL injection vulnerability.",
                feedback_on_wrong="Wrong. f-string SQL interpolation is a textbook SQL injection risk.",
            ),
            Task(
                id="e5",
                diff=Diff(
                    id="e5",
                    diff_text=(
                        "+def greet(name: str) -> str:\n"
                        '+    """Return a greeting string."""\n'
                        "+    return f'Hello, {name}!'\n"
                        "+\n"
                        "+def test_greet():\n"
                        "+    assert greet('Alice') == 'Hello, Alice!'"
                    ),
                    risk_hints=[],
                    has_tests=True,
                    touches_auth=False,
                ),
                correct_action="approve",
                correct_severity=None,
                difficulty="easy",
                feedback_on_correct="Correct! Safe, tested, well-documented utility function.",
                feedback_on_wrong="Wrong. This is a safe, well-tested function -- approve it.",
            ),
        ],

        # ── MEDIUM (5 tasks) ───────────────────────────────────────────────
        # Require understanding of auth, data handling, and concurrency.
        "medium": [
            Task(
                id="m1",
                diff=Diff(
                    id="m1",
                    diff_text=(
                        "+def get_user_profile(user_id):\n"
                        "+    user = db.get(user_id)\n"
                        "+    return user.to_dict()"
                    ),
                    risk_hints=["missing_auth"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="medium",
                feedback_on_correct="Correct! No authentication/authorization check before returning user data.",
                feedback_on_wrong="Wrong. Fetching user data without auth check is an access-control bug.",
            ),
            Task(
                id="m2",
                diff=Diff(
                    id="m2",
                    diff_text=(
                        "+def store_password(plain_password):\n"
                        "+    db.save('password', plain_password)"
                    ),
                    risk_hints=["plaintext_password"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="medium",
                feedback_on_correct="Correct! Passwords must be hashed (bcrypt/argon2) before storage.",
                feedback_on_wrong="Wrong. Storing plaintext passwords is a critical auth vulnerability.",
            ),
            Task(
                id="m3",
                diff=Diff(
                    id="m3",
                    diff_text=(
                        "+for i in range(len(items)):\n"
                        "+    process(items[i + 1])"
                    ),
                    risk_hints=["off_by_one"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="medium",
                feedback_on_correct="Correct! Accessing `items[i+1]` when i reaches last index causes IndexError.",
                feedback_on_wrong="Wrong. Off-by-one: the loop will throw IndexError on the last iteration.",
            ),
            Task(
                id="m4",
                diff=Diff(
                    id="m4",
                    diff_text=(
                        "+logger.info(f'User login attempt: user={username} token={auth_token}')"
                    ),
                    risk_hints=["logging_sensitive_data"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="medium",
                feedback_on_correct="Correct! Auth tokens must never be written to logs -- they can be extracted.",
                feedback_on_wrong="Wrong. Logging auth tokens leaks credentials into log files/systems.",
            ),
            Task(
                id="m5",
                diff=Diff(
                    id="m5",
                    diff_text=(
                        "+import threading\n"
                        "+\n"
                        "+counter = 0\n"
                        "+\n"
                        "+def increment():\n"
                        "+    global counter\n"
                        "+    counter += 1\n"
                        "+\n"
                        "+threads = [threading.Thread(target=increment) for _ in range(100)]\n"
                        "+for t in threads: t.start()\n"
                        "+for t in threads: t.join()"
                    ),
                    risk_hints=["race_condition"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="medium",
                feedback_on_correct="Correct! Unsynchronized shared counter across threads is a race condition.",
                feedback_on_wrong="Wrong. Global counter++ in multiple threads without a lock is a race condition.",
            ),
        ],

        # ── HARD (8 tasks — 5 selected per episode) ────────────────────────
        # Require deep security expertise. Frontier models should NOT ace
        # all of these on first attempt. Includes deceptive-but-safe diffs.
        "hard": [
            Task(
                id="h1",
                diff=Diff(
                    id="h1",
                    diff_text=(
                        "+def verify_token(token):\n"
                        "+    return jwt.decode(token, options={'verify_signature': False})"
                    ),
                    risk_hints=["jwt_algorithm_confusion"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="hard",
                feedback_on_correct="Correct! Disabling JWT signature verification allows token forgery.",
                feedback_on_wrong="Wrong. Skipping JWT signature verification is a critical auth bypass.",
            ),
            Task(
                id="h2",
                diff=Diff(
                    id="h2",
                    diff_text=(
                        "+import pickle\n"
                        "+\n"
                        "+def load_user_prefs(data: bytes):\n"
                        "+    return pickle.loads(data)"
                    ),
                    risk_hints=["insecure_deserialization"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="hard",
                feedback_on_correct="Correct! pickle.loads on untrusted data enables remote code execution.",
                feedback_on_wrong="Wrong. Deserializing untrusted pickle data can execute arbitrary code.",
            ),
            Task(
                id="h3",
                diff=Diff(
                    id="h3",
                    diff_text=(
                        "+import re\n"
                        "+\n"
                        "+def validate_email(email):\n"
                        r"+    pattern = r'^(a+)+@[a-z]+\.com$'" + "\n"
                        "+    return re.match(pattern, email) is not None"
                    ),
                    risk_hints=["redos"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="hard",
                feedback_on_correct="Correct! Nested quantifiers `(a+)+` cause catastrophic backtracking (ReDoS).",
                feedback_on_wrong="Wrong. The regex has nested quantifiers that cause exponential backtracking -- ReDoS.",
            ),
            Task(
                id="h4",
                diff=Diff(
                    id="h4",
                    diff_text=(
                        "+import requests\n"
                        "+\n"
                        "+def fetch_url(user_provided_url):\n"
                        "+    response = requests.get(user_provided_url)\n"
                        "+    return response.text"
                    ),
                    risk_hints=["ssrf"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="hard",
                feedback_on_correct="Correct! Fetching user-controlled URLs without allowlisting enables SSRF attacks.",
                feedback_on_wrong="Wrong. Making HTTP requests to user-controlled URLs is Server-Side Request Forgery (SSRF).",
            ),
            Task(
                id="h5",
                diff=Diff(
                    id="h5",
                    diff_text=(
                        "+def process_order(order_id: int, items: List[str]) -> dict:\n"
                        '+    """Process a customer order and return confirmation."""\n'
                        "+    validated = validate_items(items)\n"
                        "+    total = sum(get_price(i) for i in validated)\n"
                        "+    receipt = create_receipt(order_id, total)\n"
                        "+    return receipt\n"
                        "+\n"
                        "+def test_process_order():\n"
                        "+    result = process_order(1, ['apple', 'banana'])\n"
                        "+    assert 'order_id' in result\n"
                        "+    assert result['total'] > 0"
                    ),
                    risk_hints=[],
                    has_tests=True,
                    touches_auth=False,
                ),
                correct_action="approve",
                correct_severity=None,
                difficulty="hard",
                feedback_on_correct="Correct! Well-structured, tested business logic with no security concerns.",
                feedback_on_wrong="Wrong. This is a clean, well-tested function -- it should be approved.",
            ),
            # ── Extra hard tasks (added in iteration 2) ──────────────────
            Task(
                id="h6",
                diff=Diff(
                    id="h6",
                    diff_text=(
                        "+def verify_api_key(provided_key: str) -> bool:\n"
                        "+    stored_key = get_stored_key()\n"
                        "+    return provided_key == stored_key"
                    ),
                    risk_hints=["timing_attack"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! Direct string comparison with == is vulnerable to timing attacks. "
                    "Use hmac.compare_digest() instead."
                ),
                feedback_on_wrong=(
                    "Wrong. Comparing secrets with == leaks timing information -- "
                    "use hmac.compare_digest() to prevent timing attacks."
                ),
            ),
            Task(
                id="h7",
                diff=Diff(
                    id="h7",
                    diff_text=(
                        "+def read_user_file(username: str, filename: str) -> str:\n"
                        "+    path = f'/data/users/{username}/{filename}'\n"
                        "+    with open(path) as f:\n"
                        "+        return f.read()"
                    ),
                    risk_hints=["path_traversal"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! User-controlled filename allows path traversal "
                    "(e.g. '../../../etc/passwd'). Sanitize with os.path.basename()."
                ),
                feedback_on_wrong=(
                    "Wrong. Unsanitized user input in file paths enables "
                    "directory traversal attacks."
                ),
            ),
            Task(
                id="h8",
                diff=Diff(
                    id="h8",
                    diff_text=(
                        "+import hmac\n"
                        "+import hashlib\n"
                        "+\n"
                        "+def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:\n"
                        "+    expected = hmac.new(\n"
                        "+        secret.encode(), payload, hashlib.sha256\n"
                        "+    ).hexdigest()\n"
                        "+    return hmac.compare_digest(signature, expected)"
                    ),
                    risk_hints=[],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="approve",
                correct_severity=None,
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! This uses proper HMAC-SHA256 with timing-safe "
                    "comparison -- a textbook secure webhook verification."
                ),
                feedback_on_wrong=(
                    "Wrong. This is a correctly implemented webhook signature "
                    "verification using HMAC and compare_digest -- approve it."
                ),
            ),
            # ── Additional hard tasks (iteration 3) ──────────────────────
            Task(
                id="h9",
                diff=Diff(
                    id="h9",
                    diff_text=(
                        "+from rest_framework import serializers\n"
                        "+from django.contrib.auth.models import User\n"
                        "+\n"
                        "+class UserUpdateSerializer(serializers.ModelSerializer):\n"
                        "+    class Meta:\n"
                        "+        model = User\n"
                        "+        fields = '__all__'"
                    ),
                    risk_hints=["mass_assignment"],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="flag_bug",
                correct_severity="critical",
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! `fields = '__all__'` in a writable serializer allows "
                    "mass assignment — attackers can set is_staff=True or is_superuser=True."
                ),
                feedback_on_wrong=(
                    "Wrong. `fields = '__all__'` on a writable ModelSerializer exposes "
                    "privilege-escalation fields like is_staff and is_superuser."
                ),
            ),
            Task(
                id="h10",
                diff=Diff(
                    id="h10",
                    diff_text=(
                        "+from flask import Flask, redirect, request\n"
                        "+app = Flask(__name__)\n"
                        "+\n"
                        "+@app.route('/go')\n"
                        "+def safe_redirect():\n"
                        "+    next_url = request.args.get('next', '/')\n"
                        "+    return redirect(next_url)"
                    ),
                    risk_hints=["open_redirect"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
                correct_severity="medium",
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! User-controlled redirect URL with no allowlist validation "
                    "enables open redirect attacks -- validate against an allowed list."
                ),
                feedback_on_wrong=(
                    "Wrong. Redirecting to an arbitrary user-supplied URL is an open "
                    "redirect vulnerability usable for phishing."
                ),
            ),
            Task(
                id="h11",
                diff=Diff(
                    id="h11",
                    diff_text=(
                        "+import secrets\n"
                        "+import hashlib\n"
                        "+\n"
                        "+def generate_reset_token(user_id: int) -> str:\n"
                        '+    """Generate a secure password-reset token."""\n'
                        "+    token = secrets.token_urlsafe(32)\n"
                        "+    token_hash = hashlib.sha256(token.encode()).hexdigest()\n"
                        "+    store_reset_token(user_id, token_hash, expires_in=3600)\n"
                        "+    return token"
                    ),
                    risk_hints=[],
                    has_tests=False,
                    touches_auth=True,
                ),
                correct_action="approve",
                correct_severity=None,
                difficulty="hard",
                feedback_on_correct=(
                    "Correct! Uses secrets.token_urlsafe (cryptographically secure), "
                    "stores only the hash (not the raw token), and sets a 1-hour expiry."
                ),
                feedback_on_wrong=(
                    "Wrong. This is a correctly implemented reset-token flow: "
                    "cryptographically secure generation, hash-only storage, expiry -- approve it."
                ),
            ),
        ],
    }



def get_tasks(
    difficulty: Optional[str] = None,
    seed: Optional[int] = None,
    n: int = 5,
) -> Dict[str, List[Task]]:
    """
    Return tasks for the given difficulty.

    Args:
        difficulty: "easy" | "medium" | "hard".
                    If None, returns the full dict (legacy behaviour).
        seed:       Random seed for reproducible shuffling. If None, returns
                    tasks in their default order (first n).
        n:          Number of tasks to return per difficulty (default 5).

    Returns:
        If difficulty is None → Dict[str, List[Task]] (all tasks, all tiers).
        Otherwise → List[Task] of length min(n, pool_size).
    """
    all_tasks = _build_all_tasks()

    if difficulty is None:
        # Legacy: return the entire dict (each list capped at n)
        return {k: v[:n] for k, v in all_tasks.items()}

    pool = list(all_tasks.get(difficulty, all_tasks["easy"]))

    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(pool)

    return pool[:n]