from types import SimpleNamespace

from app.services.agent import FollowupAgent, _is_repetitive
from app.services.history import PatientMemory


class FakeCompletions:
    def __init__(self, content: str = "What changed since your last visit?") -> None:
        self.messages: list[dict[str, str]] = []
        self.content = content

    def create(self, **kwargs):
        self.messages = kwargs["messages"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeGroq:
    def __init__(self, content: str = "What changed since your last visit?") -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def test_agent_uses_patient_memory_for_opening() -> None:
    client = FakeGroq()
    agent = FollowupAgent(client=client, model="test-model")
    memory = PatientMemory(assessments=["2026-01-01, PHQ-9 score 8/27 (mild)"])

    result = agent.opening_question(memory)

    assert result == "What changed since your last visit?"
    assert "PHQ-9 score 8/27" in client.completions.messages[-1]["content"]
    assert "First greet the patient" in client.completions.messages[-1]["content"]


def test_agent_uses_history_and_current_conversation() -> None:
    client = FakeGroq()
    agent = FollowupAgent(client=client, model="test-model")
    memory = PatientMemory(patient_statements=["Sleep was difficult"])

    agent.followup_question(
        memory,
        [("agent", "How has sleep been?"), ("patient", "A little better")],
        "I still wake up early",
    )

    contents = [message["content"] for message in client.completions.messages]
    assert any("Sleep was difficult" in content for content in contents)
    assert contents[-1] == "I still wake up early"
    system_prompt = client.completions.messages[0]["content"]
    assert "latest patient message is primary" in system_prompt
    assert "Do not repeat or paraphrase" in system_prompt


def test_detects_paraphrased_repeated_question() -> None:
    draft = "How many afternoons this week did fatigue make it hard to focus at work?"
    previous = ["On how many afternoons has fatigue made it difficult to concentrate on work?"]
    assert _is_repetitive(draft, previous)


def test_allows_new_clinical_dimension() -> None:
    draft = "How has your appetite been lately?"
    previous = ["Has fatigue made it difficult to concentrate on work?"]
    assert not _is_repetitive(draft, previous)


def test_extracts_source_grounded_symptoms_for_report() -> None:
    client = FakeGroq(
        '{"summary":"Sleep improved; fatigue persists.","symptoms":['
        '{"symptom":"fatigue","change":"unchanged","timeframe":"afternoons",'
        '"impact":"work is difficult","evidence":"I still feel tired at work"}]}'
    )
    agent = FollowupAgent(client=client, model="test-model")

    findings = agent.extract_report_findings(
        [("agent", "How are you?"), ("patient", "I still feel tired at work")]
    )

    assert findings.summary == "Sleep improved; fatigue persists."
    assert findings.symptoms[0].symptom == "fatigue"
    assert findings.symptoms[0].evidence == "I still feel tired at work"