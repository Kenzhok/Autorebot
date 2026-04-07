from typing import Dict, List
from pydantic import BaseModel
import importlib, sys

# Always resolve Diff from the same module object to avoid Pydantic
# "two different classes" validation errors when sys.path varies.
# Priority: package import → direct import → code_review_env package import
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
    correct_action: str  # flag_bug | approve | ignore
    difficulty: str
    feedback_on_correct: str = ""
    feedback_on_wrong: str = ""


def get_tasks() -> Dict[str, List[Task]]:
    return {

        # ── EASY (5 tasks) ─────────────────────────────────────────────────
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
                        "+    \"\"\"Return a greeting string.\"\"\"\n"
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
                difficulty="easy",
                feedback_on_correct="Correct! Safe, tested, well-documented utility function.",
                feedback_on_wrong="Wrong. This is a safe, well-tested function -- approve it.",
            ),
        ],

        # ── MEDIUM (5 tasks) ───────────────────────────────────────────────
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
                difficulty="medium",
                feedback_on_correct="Correct! Unsynchronized shared counter across threads is a race condition.",
                feedback_on_wrong="Wrong. Global counter++ in multiple threads without a lock is a race condition.",
            ),
        ],

        # ── HARD (5 tasks) ─────────────────────────────────────────────────
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
                        "+    pattern = r'^(a+)+@[a-z]+\\.com$'\n"
                        "+    return re.match(pattern, email) is not None"
                    ),
                    risk_hints=["redos"],
                    has_tests=False,
                    touches_auth=False,
                ),
                correct_action="flag_bug",
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
                        "+    \"\"\"Process a customer order and return confirmation.\"\"\"\n"
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
                difficulty="hard",
                feedback_on_correct="Correct! Well-structured, tested business logic with no security concerns.",
                feedback_on_wrong="Wrong. This is a clean, well-tested function -- it should be approved.",
            ),
        ],
    }