import pytest
from fastapi.testclient import TestClient
from models import Base, engine
from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_nodes_api():
    res = client.post("/nodes", json={"name": "ServerA"})
    assert res.status_code == 201
    assert res.json() == {"id": 1, "name": "ServerA"}

    res_dup = client.post("/nodes", json={"name": "ServerA"})
    assert res_dup.status_code == 400

    res_empty = client.post("/nodes", json={})
    assert res_empty.status_code == 400

def test_edges_and_shortest_route():
    client.post("/nodes", json={"name": "ServerA"})
    client.post("/nodes", json={"name": "ServerB"})
    client.post("/nodes", json={"name": "ServerD"})
    client.post("/nodes", json={"name": "LonelyServer"})

    res_edge = client.post("/edges", json={"source": "ServerA", "destination": "ServerB", "latency": 12.5})
    assert res_edge.status_code == 201
    client.post("/edges", json={"source": "ServerB", "destination": "ServerD", "latency": 10.9})

    assert client.post("/edges", json={"source": "ServerA", "destination": "ServerD", "latency": -5}).status_code == 400

    res_route = client.post("/routes/shortest", json={"source": "ServerA", "destination": "ServerD"})
    assert res_route.status_code == 200
    assert res_route.json() == {"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]}

    res_404 = client.post("/routes/shortest", json={"source": "ServerA", "destination": "LonelyServer"})
    assert res_404.status_code == 404
    assert res_404.json() == {"error": "No path exists between ServerA and LonelyServer"}

    res_hist = client.get("/routes/history?source=ServerA")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) == 1
    assert res_hist.json()[0]["total_latency"] == 23.4