import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache

from groq import Groq

from app.config import get_settings
from app.services.history import PatientMemory


SYSTEM_PROMPT = """You are a patient follow-up conversation agent operating inside a
clinician-supervised workflow. Respond naturally to the patient's latest message, then ask
at most one concise and relevant next question.

Conversation rules:
- The latest patient message is primary. Use stored memory only when it is relevant to that message.
- Briefly acknowledge what the patient said before asking a question.
- For a greeting or small talk, greet the patient and ask a broad check-in question; do not force an old symptom into the reply.
- Interpret short answers such as yes, no, or a number as answers to the immediately preceding agent question.
- Progress to a new clinical dimension after an answer. Do not repeat or paraphrase any recent agent question.
- Refer naturally to prior symptoms when useful, but never invent history.
- Ask one question at a time. Do not diagnose, recommend treatment, change PHQ-9 wording or scoring, or make emergency determinations.
- Do not request identifying information."""


class AgentUnavailableError(RuntimeError):
    pass


@dataclass
class SymptomFinding:
    symptom: str
    change: str = "Not specified"
    timeframe: str = "Not specified"
    impact: str = "Not specified"
    evidence: str = ""


@dataclass
class ConversationFindings:
    summary: str = "No symptoms were explicitly reported in the conversation."
    symptoms: list[SymptomFinding] = field(default_factory=list)


def _redact_common_identifiers(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email removed]", text)
    text = re.sub(r"\b(?:\+?\d[\d .()-]{7,}\d)\b", "[phone removed]", text)
    return text[:4000]


def _is_repetitive(draft: str, previous_questions: list[str]) -> bool:
    normalized_draft = re.sub(r"[^a-z0-9 ]", "", draft.lower())
    for question in previous_questions:
        normalized_question = re.sub(r"[^a-z0-9 ]", "", question.lower())
        if SequenceMatcher(None, normalized_draft, normalized_question).ratio() >= 0.62:
            return True
    return False


class FollowupAgent:
    def __init__(self, client: Groq | None = None, model: str | None = None) -> None:
        settings = get_settings()
        if client is None and not settings.groq_api_key:
            raise AgentUnavailableError(
                "Groq is not configured. Add GROQ_API_KEY to backend/.env and restart the API."
            )
        self.client = client or Groq(api_key=settings.groq_api_key)
        self.model = model or settings.groq_model

    def _complete(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.25,
                max_completion_tokens=512,
                reasoning_effort="low",
                reasoning_format="hidden",
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                raise AgentUnavailableError("Groq returned an empty response")
            return content.strip()
        except AgentUnavailableError:
            raise
        except Exception as exc:
            raise AgentUnavailableError("Groq could not generate a response") from exc

    def opening_question(self, memory: PatientMemory) -> str:
        prompt = (
            "Start a new consultation. First greet the patient warmly and briefly. "
            "If previous history exists, welcome them back, then naturally mention only "
            "the most relevant prior concern and ask one follow-up question. If there is "
            "no history, greet them and ask one appropriate broad opening question. "
            "Never begin directly with a symptom or question before the greeting.\n\n"
            f"PATIENT MEMORY\n{_redact_common_identifiers(memory.to_prompt())}"
        )
        return self._complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )

    def followup_question(
        self,
        memory: PatientMemory,
        conversation: list[tuple[str, str]],
        patient_message: str,
    ) -> str:
        memory_text = _redact_common_identifiers(memory.to_prompt())
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"{SYSTEM_PROMPT}\n\nBACKGROUND PATIENT MEMORY\n{memory_text}\n\n"
                    "The memory above is background, not the current patient message."
                ),
            }
        ]
        for role, content in conversation[-10:]:
            messages.append(
                {
                    "role": "assistant" if role == "agent" else "user",
                    "content": _redact_common_identifiers(content),
                }
            )
        messages.append(
            {"role": "user", "content": _redact_common_identifiers(patient_message)}
        )
        draft = self._complete(messages)
        previous_questions = [
            content for role, content in conversation[-20:] if role == "agent"
        ]
        if not _is_repetitive(draft, previous_questions):
            return draft
        messages.extend(
            [
                {"role": "assistant", "content": draft},
                {
                    "role": "user",
                    "content": (
                        "That draft is too similar to a question already asked. "
                        "Acknowledge my latest message and ask one question about a different "
                        "relevant dimension that has not been covered."
                    ),
                },
            ]
        )
        return self._complete(messages)

    def extract_report_findings(
        self, conversation: list[tuple[str, str]]
    ) -> ConversationFindings:
        patient_statements = [
            content for role, content in conversation if role in {"patient", "clinician"}
        ]
        if not patient_statements:
            return ConversationFindings()
        transcript = "\n".join(
            f"{role}: {_redact_common_identifiers(content)}"
            for role, content in conversation[-40:]
        )[-12000:]
        prompt = f"""Extract report findings from this consultation transcript.
Return JSON only with this exact structure:
{{
    "summary": "detailed source-grounded consultation narrative",
  "symptoms": [
    {{
      "symptom": "symptom stated by the patient",
      "change": "new, improved, worsened, unchanged, or not specified",
      "timeframe": "timeframe stated by the patient or Not specified",
      "impact": "daily impact stated by the patient or Not specified",
      "evidence": "short exact patient statement supporting this finding"
    }}
  ]
}}

Rules:
- Extract only symptoms explicitly stated by the patient. Never infer a diagnosis.
- Agent questions are context only and are not evidence that a symptom exists.
- Do not invent severity, duration, impact, or improvement.
- Merge duplicate references to the same symptom and keep the latest stated change.
- If no symptom is stated, return an empty symptoms list.
- Write the summary as one coherent paragraph of 3 to 5 complete sentences.
- Describe the patient's main concerns, stated timing, progression or change, daily impact,
  and other relevant patient-reported context when those details are present.
- Distinguish current concerns from symptoms the patient says have improved or resolved.
- Omit details that were only asked about but never confirmed by the patient.
- Do not include speaker labels, bullet points, recommendations, or diagnoses.

TRANSCRIPT
{transcript}"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You extract source-grounded clinical conversation facts without diagnosing.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_completion_tokens=900,
                reasoning_effort="low",
                reasoning_format="hidden",
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content or "{}")
            symptoms = []
            for item in data.get("symptoms", [])[:12]:
                if not isinstance(item, dict) or not str(item.get("symptom", "")).strip():
                    continue
                symptoms.append(
                    SymptomFinding(
                        symptom=str(item["symptom"]).strip()[:200],
                        change=str(item.get("change") or "Not specified").strip()[:100],
                        timeframe=str(item.get("timeframe") or "Not specified").strip()[:200],
                        impact=str(item.get("impact") or "Not specified").strip()[:300],
                        evidence=str(item.get("evidence") or "").strip()[:500],
                    )
                )
            summary = str(data.get("summary") or "").strip()[:1000]
            return ConversationFindings(
                summary=summary or "No symptoms were explicitly reported in the conversation.",
                symptoms=symptoms,
            )
        except Exception as exc:
            raise AgentUnavailableError(
                "Groq could not extract conversation findings for the report"
            ) from exc


@lru_cache
def get_followup_agent() -> FollowupAgent:
    return FollowupAgent()