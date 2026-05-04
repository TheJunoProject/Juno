"""Intent classifier — Path A vs Path B routing for the Interactive Layer.

Per `docs/agent-architecture.md` §6.1, the classifier:
1. Decides whether the turn is a direct conversational answer (Path A)
   or needs the Agentic Layer (Path B).
2. Emits which available context reports are relevant to the user's
   message — these are loaded just-in-time, not on every turn.

Phase 4 implements the classifier as a tight prompt to the model
configured for `task_type=intent_classification`. The user can route
this to a smaller / faster model than `conversational` if they have
one. Phase 8 may swap this for a fine-tuned classifier (LoRA) — the
interface stays the same.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from server.inference import InferenceRequest, InferenceRouter, Message
from server.skills import SkillRegistry

log = logging.getLogger(__name__)


@dataclass
class IntentDecision:
    path: str  # "direct" | "agentic"
    skills: list[str]  # hint set; the agentic loop is free to ignore
    reports: list[str]  # report stems to load (e.g. ["news", "calendar"])
    rationale: str = ""


CLASSIFIER_SYSTEM_PROMPT = """\
You are Juno's intent classifier. For every user turn, decide:

1. path: "direct" if the user's request can be answered conversationally
   from your training knowledge plus any provided context. "agentic" if
   it requires calling tools to look up live information, read or write
   files, control the user's machine, or take an action with side
   effects.
2. skills: a possibly-empty list of skill names that look relevant.
   Choose only from the skill list in the user message.
3. reports: a possibly-empty list of context report stems to load.
   Choose only from the list in the user message. Examples:
   - calendar/time questions  -> ["calendar"]
   - email questions          -> ["email-digest"]
   - news questions           -> ["news"]
   Open-ended chat            -> []
4. rationale: one short sentence.

Output JSON only, no prose. Schema:

{
  "path": "direct" | "agentic",
  "skills": [string, ...],
  "reports": [string, ...],
  "rationale": string
}
"""


class IntentClassifier:
    def __init__(
        self,
        router: InferenceRouter,
        skills: SkillRegistry,
    ) -> None:
        self._router = router
        self._skills = skills

    async def classify(
        self,
        user_message: str,
        *,
        available_reports: list[str],
    ) -> IntentDecision:
        skill_names = self._skills.names()
        request = InferenceRequest(
            messages=[
                Message(role="system", content=CLASSIFIER_SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=self._build_user_prompt(
                        user_message,
                        skill_names=skill_names,
                        report_stems=available_reports,
                    ),
                ),
            ],
            task_type="intent_classification",
            temperature=0.0,
            response_format_json=True,
        )
        try:
            response = await self._router.complete(request)
        except Exception as e:
            log.warning("Intent classifier failed; defaulting to direct path: %s", e)
            return _default_direct(reports=available_reports)

        decision = _parse(response.content)
        return _validate(decision, skill_names=skill_names, report_stems=available_reports)

    def _build_user_prompt(
        self,
        user_message: str,
        *,
        skill_names: list[str],
        report_stems: list[str],
    ) -> str:
        return (
            f"Available skills: {skill_names or '[]'}\n"
            f"Available reports: {report_stems or '[]'}\n\n"
            f'User message:\n"""\n{user_message}\n"""'
        )


# ---- helpers ------------------------------------------------------------


def _parse(content: str) -> dict:
    """Parse the classifier's JSON output. Empty / malformed -> {}."""
    text = (content or "").strip()
    if not text:
        return {}
    # Models sometimes wrap JSON in markdown fences despite being told not
    # to; strip a code fence if present.
    if text.startswith("```"):
        text = text.strip("`")
        # After stripping backticks the optional language tag may remain.
        if text.startswith("json\n"):
            text = text[5:]
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        log.debug("Intent classifier returned non-JSON: %r", content[:200])
        return {}


def _validate(
    raw: dict,
    *,
    skill_names: list[str],
    report_stems: list[str],
) -> IntentDecision:
    """Coerce model output into a safe IntentDecision.

    Unknown skills / reports are filtered out so the downstream Agentic
    Layer doesn't try to dispatch a skill that doesn't exist.
    """
    path = raw.get("path")
    if path not in {"direct", "agentic"}:
        path = "direct"
    skills = [s for s in (raw.get("skills") or []) if s in skill_names]
    reports = [r for r in (raw.get("reports") or []) if r in report_stems]
    rationale = str(raw.get("rationale") or "")
    return IntentDecision(
        path=path,
        skills=skills,
        reports=reports,
        rationale=rationale,
    )


def _default_direct(*, reports: list[str]) -> IntentDecision:
    """Safe fallback when classification fails — answer directly, load
    no reports. Better to give a less-grounded answer than to crash on
    every turn because of a flaky classifier model."""
    return IntentDecision(
        path="direct", skills=[], reports=[], rationale="classifier unavailable"
    )
