import os
import sys
from openai import OpenAI
try:
    from .models import CodeReviewAction
except ImportError:
    from models import CodeReviewAction


# ── LLM client (lazy init) ────────────────────────────────────────────────────
_llm_client = None

def _get_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        api_base = os.environ.get("API_BASE_URL", "")
        api_key  = os.environ.get("HF_TOKEN", "hf-no-token")
        model    = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

        if not api_base:
            print(
                "[WARN] API_BASE_URL not set -- LLMAgent will fall back to rule-based logic.",
                file=sys.stderr,
            )
            return None  # signals fallback

        _llm_client = OpenAI(base_url=api_base, api_key=api_key)
    return _llm_client


VALID_ACTIONS = {"flag_bug", "approve", "ignore"}
MODEL_NAME    = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")


class LLMAgent:
    def __init__(self):
        self.history = []  # stores past mistakes for in-context learning

    # ── Prompt builder ────────────────────────────────────────────────────────
    def build_prompt(self, observation) -> str:
        diff = observation.current_diff

        # Inject last 3 mistakes as few-shot negative examples
        history_text = ""
        if self.history:
            history_text = "\nPrevious mistakes to avoid:\n"
            for h in self.history[-3:]:
                history_text += (
                    f"  - You chose '{h['action']}' on a diff that "
                    f"touches_auth={h['touches_auth']}, has_tests={h['has_tests']}, "
                    f"risk_hints={h['risk_hints']}. That was wrong -- avoid repeating it.\n"
                )

        prompt = f"""You are a senior software engineer performing a code review.

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
{history_text}
Rules:
- If security or auth logic is changed without tests -> flag_bug
- If there is SQL string concatenation or f-string interpolation -> flag_bug
- If credentials or tokens are hardcoded -> flag_bug
- If the diff is clearly safe and well-tested -> approve
- If it is only a style issue -> ignore

Respond in this EXACT format (two lines only):
ACTION: <flag_bug|approve|ignore>
COMMENT: <one sentence explanation>"""
        return prompt

    # ── LLM call (with rule-based fallback) ───────────────────────────────────
    def call_llm(self, observation) -> tuple[str, str]:
        """
        Call the LLM with the built prompt.
        Returns (action_type, comment).
        Falls back to rule-based logic if API_BASE_URL is not set or call fails.
        """
        client = _get_client()

        # ── Fallback: rule-based if no client ─────────────────────────────────
        if client is None:
            return self._rule_based_fallback(observation), ""

        prompt = self.build_prompt(observation)

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[WARN] LLM call failed: {e} -- falling back to rules.", file=sys.stderr)
            return self._rule_based_fallback(observation), ""

        # ── Parse response ─────────────────────────────────────────────────────
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

    # ── Rule-based fallback (used when no LLM is available) ───────────────────
    def _rule_based_fallback(self, observation) -> str:
        diff = observation.current_diff

        # Check history for matching past mistakes -- flag to be safe
        for h in self.history[-5:]:
            if (
                h["touches_auth"] == diff.touches_auth
                and h["has_tests"] == diff.has_tests
                and h["risk_hints"] == diff.risk_hints
            ):
                return "flag_bug"

        if diff.touches_auth:
            return "flag_bug"
        if not diff.has_tests:
            return "flag_bug"
        if diff.risk_hints:
            return "flag_bug"
        return "approve"

    # ── Act ───────────────────────────────────────────────────────────────────
    def act(self, observation) -> CodeReviewAction:
        action_type, comment = self.call_llm(observation)
        return CodeReviewAction(action_type=action_type.strip(), comment=comment)

    # ── Learn (store mistakes for future few-shot context) ────────────────────
    def learn(self, action: CodeReviewAction, observation):
        """
        If the last action resulted in a negative reward, record it as a mistake.
        These mistakes are injected into future prompts as few-shot negative examples.
        """
        if observation.reward < 0:
            diff = observation.current_diff
            self.history.append({
                "action":       action.action_type,
                "touches_auth": diff.touches_auth,
                "has_tests":    diff.has_tests,
                "risk_hints":   diff.risk_hints,
                "feedback":     observation.feedback,
            })