from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import Base, engine, get_db, Node, Edge, RouteHistory
from services import find_shortest_path

Base.metadata.create_all(bind=engine)
app = FastAPI()

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": "Invalid or missing input fields"})

class NodeRequest(BaseModel):
    name: Optional[str] = None

class EdgeRequest(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None
    latency: Optional[float] = None

class RouteRequest(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None

@app.post("/nodes", status_code=201)
def add_node(body: NodeRequest, db: Session = Depends(get_db)):
    if not body.name or not body.name.strip():
        return JSONResponse(status_code=400, content={"error": "Name is missing"})

    if db.query(Node).filter(Node.name == body.name).first():
        return JSONResponse(status_code=400, content={"error": "Duplicate node"})

    node = Node(name=body.name)
    db.add(node)
    db.commit()
    db.refresh(node)
    return {"id": node.id, "name": node.name}

@app.post("/edges", status_code=201)
def add_edge(body: EdgeRequest, db: Session = Depends(get_db)):
    if not body.source or not body.destination or body.latency is None:
        return JSONResponse(status_code=400, content={"error": "Source, destination, or latency missing"})

    if body.latency <= 0:
        return JSONResponse(status_code=400, content={"error": "Latency must be > 0"})

    src = db.query(Node).filter(Node.name == body.source).first()
    dst = db.query(Node).filter(Node.name == body.destination).first()
    if not src or not dst:
        return JSONResponse(status_code=400, content={"error": "Nodes not found"})

    dup = db.query(Edge).filter(Edge.source == body.source, Edge.destination == body.destination).first()
    if dup:
        return JSONResponse(status_code=400, content={"error": "Duplicate edge"})

    edge = Edge(source=body.source, destination=body.destination, latency=body.latency)
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return {"id": edge.id, "source": edge.source, "destination": edge.destination, "latency": edge.latency}

@app.post("/routes/shortest", status_code=200)
def get_shortest_route(body: RouteRequest, db: Session = Depends(get_db)):
    if not body.source or not body.destination:
        return JSONResponse(status_code=400, content={"error": "Invalid nodes"})

    src = db.query(Node).filter(Node.name == body.source).first()
    dst = db.query(Node).filter(Node.name == body.destination).first()
    if not src or not dst:
        return JSONResponse(status_code=400, content={"error": "Non-existent nodes"})

    edges = db.query(Edge).all()
    total_latency, path = find_shortest_path(edges, body.source, body.destination)

    if path is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No path exists between {body.source} and {body.destination}"}
        )

    history = RouteHistory(
        source=body.source, destination=body.destination, total_latency=total_latency, path=path
    )
    db.add(history)
    db.commit()

    return {"total_latency": total_latency, "path": path}

@app.get("/routes/history", status_code=200)
def get_history(
    source: Optional[str] = None,
    destination: Optional[str] = None,
    limit: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(RouteHistory)
    if source:
        query = query.filter(RouteHistory.source == source)
    if destination:
        query = query.filter(RouteHistory.destination == destination)
    if date_from:
        query = query.filter(RouteHistory.created_at >= date_from)
    if date_to:
        query = query.filter(RouteHistory.created_at <= date_to)
    if limit:
        query = query.limit(limit)

    records = query.all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "destination": r.destination,
            "total_latency": r.total_latency,
            "path": r.path,
            "created_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for r in records
    ]

@app.get("/nodes")
def list_nodes(db: Session = Depends(get_db)):
    return [{"id": n.id, "name": n.name} for n in db.query(Node).all()]

@app.get("/edges")
def list_edges(db: Session = Depends(get_db)):
    return [
        {"id": e.id, "source": e.source, "destination": e.destination, "latency": e.latency}
        for e in db.query(Edge).all()
    ]

@app.delete("/nodes/{id}")
def delete_node(id: int, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == id).first()
    if not node:
        return JSONResponse(status_code=404, content={"error": "Node not found"})
    db.query(Edge).filter((Edge.source == node.name) | (Edge.destination == node.name)).delete()
    db.delete(node)
    db.commit()
    return {"message": "Node deleted"}

@app.delete("/edges/{id}")
def delete_edge(id: int, db: Session = Depends(get_db)):
    edge = db.query(Edge).filter(Edge.id == id).first()
    if not edge:
        return JSONResponse(status_code=404, content={"error": "Edge not found"})
    db.delete(edge)
    db.commit()
    return {"message": "Edge deleted"}