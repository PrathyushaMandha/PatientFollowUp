from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def require_success(response, expected_status: int = 200):
    if response.status_code != expected_status:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    client = TestClient(app)
    suffix = uuid4().hex[:8]
    settings = get_settings()

    bootstrap = client.post("/api/auth/bootstrap")
    if bootstrap.status_code == 201:
        token = bootstrap.json()["access_token"]
    else:
        login = client.post(
            "/api/auth/login",
            data={
                "username": settings.bootstrap_username,
                "password": settings.bootstrap_password,
            },
        )
        token = require_success(login)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient = require_success(
        client.post(
            "/api/patients",
            headers=headers,
            json={
                "first_name": "Synthetic",
                "last_name": f"Patient-{suffix}",
                "date_of_birth": "1990-01-01",
                "portal_username": f"patient-{suffix}",
                "portal_password": "SyntheticPass123!",
            },
        ),
        201,
    )
    patient_id = patient["public_id"]

    first = require_success(
        client.post(f"/api/patients/{patient_id}/consultations", headers=headers), 201
    )
    first_assessment = require_success(
        client.post(f"/api/consultations/{first['public_id']}/assessments", headers=headers),
        201,
    )
    first_scores = [0, 1, 2, 2, 0, 0, 1, 0, 0]
    for number, score in enumerate(first_scores, start=1):
        first_result = require_success(
            client.post(
                f"/api/assessments/{first_assessment['public_id']}/answers",
                headers=headers,
                json={"question_number": number, "score": score},
            )
        )
    assert first_result["assessment"]["total_score"] == sum(first_scores)
    require_success(client.post(f"/api/consultations/{first['public_id']}/complete", headers=headers))

    second = require_success(
        client.post(f"/api/patients/{patient_id}/consultations", headers=headers), 201
    )
    opening = second["messages"][0]["content"].lower()
    assert "previous consultation" in opening
    second_assessment = require_success(
        client.post(f"/api/consultations/{second['public_id']}/assessments", headers=headers),
        201,
    )
    second_scores = [0, 0, 1, 1, 0, 0, 0, 0, 1]
    for number, score in enumerate(second_scores, start=1):
        second_result = require_success(
            client.post(
                f"/api/assessments/{second_assessment['public_id']}/answers",
                headers=headers,
                json={"question_number": number, "score": score},
            )
        )
    assert second_result["safety_alert"] is True
    assert second_result["assessment"]["total_score"] == sum(second_scores)

    history = require_success(
        client.get(f"/api/patients/{patient_id}/assessment-history", headers=headers)
    )
    assert len(history) == 2
    assert history[1]["score_change"] == sum(second_scores) - sum(first_scores)
    safety_events = require_success(client.get("/api/safety-events", headers=headers))
    assert any(event["consultation_id"] for event in safety_events)
    print(f"Milestone verified for synthetic patient {patient_id}")


if __name__ == "__main__":
    main()