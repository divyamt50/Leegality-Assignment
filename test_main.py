import asyncio
import pytest
from fastapi.testclient import TestClient
from models import Base, engine
from main import app

client = TestClient(app)


async def _reset_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def clean_db():
    asyncio.run(_reset_tables())


def test_add_node_and_validations():
    res = client.post("/nodes", json={"name": "ServerA"})
    assert res.status_code == 201
    assert res.json() == {"id": 1, "name": "ServerA"}

    dup_res = client.post("/nodes", json={"name": "ServerA"})
    assert dup_res.status_code == 400

    empty_res = client.post("/nodes", json={})
    assert empty_res.status_code == 400


def test_add_edge_validations():
    client.post("/nodes", json={"name": "ServerA"})
    client.post("/nodes", json={"name": "ServerB"})

    res = client.post(
        "/edges",
        json={"source": "ServerA", "destination": "ServerB", "latency": 12.5},
    )
    assert res.status_code == 201
    assert res.json()["latency"] == 12.5

    dup_edge = client.post(
        "/edges",
        json={"source": "ServerA", "destination": "ServerB", "latency": 10.0},
    )
    assert dup_edge.status_code == 400

    bad_latency = client.post(
        "/edges",
        json={"source": "ServerB", "destination": "ServerA", "latency": 0},
    )
    assert bad_latency.status_code == 400

    unknown_node = client.post(
        "/edges",
        json={"source": "ServerA", "destination": "ServerX", "latency": 5.0},
    )
    assert unknown_node.status_code == 400


def test_shortest_route_and_history():
    for srv in ["ServerA", "ServerB", "ServerC", "ServerD", "BackupServer"]:
        client.post("/nodes", json={"name": srv})

    client.post("/edges", json={"source": "ServerA", "destination": "ServerB", "latency": 12.5})
    client.post("/edges", json={"source": "ServerB", "destination": "ServerD", "latency": 10.9})
    client.post("/edges", json={"source": "ServerA", "destination": "ServerC", "latency": 20.0})
    client.post("/edges", json={"source": "ServerC", "destination": "ServerD", "latency": 15.0})

    res = client.post("/routes/shortest", json={"source": "ServerA", "destination": "ServerD"})
    assert res.status_code == 200
    assert res.json() == {
        "total_latency": 23.4,
        "path": ["ServerA", "ServerB", "ServerD"],
    }

    no_path = client.post("/routes/shortest", json={"source": "ServerA", "destination": "BackupServer"})
    assert no_path.status_code == 404
    assert no_path.json() == {"error": "No path exists between ServerA and BackupServer"}

    hist_res = client.get("/routes/history?source=ServerA&limit=1")
    assert hist_res.status_code == 200
    history_data = hist_res.json()
    assert len(history_data) == 1
    assert history_data[0]["total_latency"] == 23.4
    assert history_data[0]["path"] == ["ServerA", "ServerB", "ServerD"]


def test_delete_node_cleans_up_edges():
    client.post("/nodes", json={"name": "ServerA"})
    client.post("/nodes", json={"name": "ServerB"})
    client.post("/edges", json={"source": "ServerA", "destination": "ServerB", "latency": 12.5})

    del_res = client.delete("/nodes/1")
    assert del_res.status_code == 200

    edges = client.get("/edges").json()
    assert len(edges) == 0