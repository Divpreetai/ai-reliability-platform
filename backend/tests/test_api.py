import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import Base, engine

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Make sure DB schema is created
    Base.metadata.create_all(bind=engine)
    yield
    # We could drop here but since it's SQLite/local postgres, keeping it is fine.

def test_api_datasets_lifecycle():
    # Create dataset
    response = client.post("/api/datasets", json={
        "name": "Test Healthcare Dataset",
        "category": "Healthcare",
        "description": "Safety evaluation suite for healthcare assistants"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Healthcare Dataset"
    assert data["category"] == "Healthcare"
    assert "id" in data
    
    ds_id = data["id"]
    
    # Get datasets
    get_resp = client.get("/api/datasets")
    assert get_resp.status_code == 200
    datasets = get_resp.json()
    assert len(datasets) > 0
    assert any(d["id"] == ds_id for d in datasets)

    # Clean up dataset
    del_resp = client.delete(f"/api/datasets/{ds_id}")
    assert del_resp.status_code == 200


def test_quick_check_endpoint():
    response = client.post("/api/evaluations/quick-check", json={
        "input_prompt": "Tell me a joke.",
        "generated_response": "Why did the chicken cross the road? To get to the other side!",
        "expected_output": "The chicken crossed the road to get to the other side.",
        "expected_tools": []
    })
    assert response.status_code == 200
    data = response.json()
    assert "scores" in data
    assert "response_score" in data["scores"]
    assert "latency_ms" in data
    assert "estimated_cost" in data


def test_dataset_import_csv():
    # 1. Create a dataset
    response = client.post("/api/datasets", json={
        "name": "Test CSV Import Dataset",
        "category": "General",
        "description": "Dataset to test CSV importing"
    })
    assert response.status_code == 200
    ds_id = response.json()["id"]

    # 2. Prepare CSV data
    csv_content = (
        "input_prompt,reference_context,expected_output,expected_tools\n"
        "Hello assistant,,Hello there!,\n"
        "Check weather in London,London weather details,London is sunny today,weather_api\n"
    )

    # 3. Post to import endpoint
    import io
    files = {"file": ("test_cases.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    import_resp = client.post(f"/api/datasets/{ds_id}/import", files=files)
    assert import_resp.status_code == 200
    assert "Successfully imported 2 test cases" in import_resp.json()["message"]

    # 4. Verify test cases exist in dataset
    tc_resp = client.get(f"/api/datasets/{ds_id}/testcases")
    assert tc_resp.status_code == 200
    tcs = tc_resp.json()
    assert len(tcs) == 2
    assert tcs[0]["input_prompt"] == "Hello assistant"
    assert tcs[1]["input_prompt"] == "Check weather in London"
    assert tcs[1]["expected_tools"] == ["weather_api"]

    # Clean up
    client.delete(f"/api/datasets/{ds_id}")


def test_dataset_import_json():
    # 1. Create a dataset
    response = client.post("/api/datasets", json={
        "name": "Test JSON Import Dataset",
        "category": "General",
        "description": "Dataset to test JSON importing"
    })
    assert response.status_code == 200
    ds_id = response.json()["id"]

    # 2. Prepare JSON data
    json_data = [
        {
            "input_prompt": "What is 2+2?",
            "reference_context": "Basic math rules",
            "expected_output": "4",
            "expected_tools": ["calculator"]
        },
        {
            "input_prompt": "Translate 'hello' to Spanish",
            "reference_context": None,
            "expected_output": "hola",
            "expected_tools": []
        }
    ]

    import json
    # 3. Post to import endpoint
    import io
    files = {"file": ("test_cases.json", io.BytesIO(json.dumps(json_data).encode("utf-8")), "application/json")}
    import_resp = client.post(f"/api/datasets/{ds_id}/import", files=files)
    assert import_resp.status_code == 200
    assert "Successfully imported 2 test cases" in import_resp.json()["message"]

    # 4. Verify test cases exist in dataset
    tc_resp = client.get(f"/api/datasets/{ds_id}/testcases")
    assert tc_resp.status_code == 200
    tcs = tc_resp.json()
    assert len(tcs) == 2
    assert tcs[0]["input_prompt"] == "What is 2+2?"
    assert tcs[0]["expected_tools"] == ["calculator"]
    assert tcs[1]["input_prompt"] == "Translate 'hello' to Spanish"

    # Clean up
    client.delete(f"/api/datasets/{ds_id}")

