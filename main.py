from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Base, engine, get_db, Node, Edge, RouteHistory
from services import calculate_shortest_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Network Route Optimization Service", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request payload or missing fields"},
    )


class NodePayload(BaseModel):
    name: Optional[str] = None


class EdgePayload(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None
    latency: Optional[float] = None


class ShortestRoutePayload(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None


@app.post("/nodes", status_code=201)
async def create_node(payload: NodePayload, db: AsyncSession = Depends(get_db)):
    if not payload.name or not payload.name.strip():
        return JSONResponse(status_code=400, content={"error": "Node name is required"})

    clean_name = payload.name.strip()
    res = await db.execute(select(Node).where(Node.name == clean_name))
    if res.scalar_one_or_none():
        return JSONResponse(status_code=400, content={"error": "Node with this name already exists"})

    new_node = Node(name=clean_name)
    db.add(new_node)
    await db.commit()
    await db.refresh(new_node)

    return {"id": new_node.id, "name": new_node.name}


@app.post("/edges", status_code=201)
async def create_edge(payload: EdgePayload, db: AsyncSession = Depends(get_db)):
    if not payload.source or not payload.destination or payload.latency is None:
        return JSONResponse(
            status_code=400,
            content={"error": "source, destination and latency are required"},
        )

    if payload.latency <= 0:
        return JSONResponse(status_code=400, content={"error": "latency must be greater than 0"})

    if payload.source == payload.destination:
        return JSONResponse(status_code=400, content={"error": "source and destination cannot be same"})

    src_res = await db.execute(select(Node).where(Node.name == payload.source))
    dst_res = await db.execute(select(Node).where(Node.name == payload.destination))
    if not src_res.scalar_one_or_none() or not dst_res.scalar_one_or_none():
        return JSONResponse(status_code=400, content={"error": "Source or destination node not found"})

    dup_res = await db.execute(
        select(Edge).where(
            Edge.source == payload.source,
            Edge.destination == payload.destination,
        )
    )
    if dup_res.scalar_one_or_none():
        return JSONResponse(status_code=400, content={"error": "Edge already exists between these nodes"})

    new_edge = Edge(
        source=payload.source,
        destination=payload.destination,
        latency=payload.latency,
    )
    db.add(new_edge)
    await db.commit()
    await db.refresh(new_edge)

    return {
        "id": new_edge.id,
        "source": new_edge.source,
        "destination": new_edge.destination,
        "latency": new_edge.latency,
    }


@app.post("/routes/shortest", status_code=200)
async def get_shortest_route(payload: ShortestRoutePayload, db: AsyncSession = Depends(get_db)):
    if not payload.source or not payload.destination:
        return JSONResponse(status_code=400, content={"error": "source and destination are required"})

    src_res = await db.execute(select(Node).where(Node.name == payload.source))
    dst_res = await db.execute(select(Node).where(Node.name == payload.destination))
    if not src_res.scalar_one_or_none() or not dst_res.scalar_one_or_none():
        return JSONResponse(status_code=400, content={"error": "Invalid or non-existent nodes"})

    edges_res = await db.execute(select(Edge))
    all_edges = edges_res.scalars().all()

    total_latency, path = calculate_shortest_path(all_edges, payload.source, payload.destination)

    if path is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No path exists between {payload.source} and {payload.destination}"},
        )

    history_entry = RouteHistory(
        source=payload.source,
        destination=payload.destination,
        total_latency=total_latency,
        path=path,
    )
    db.add(history_entry)
    await db.commit()

    return {
        "total_latency": total_latency,
        "path": path,
    }


@app.get("/routes/history", status_code=200)
async def get_route_history(
    source: Optional[str] = None,
    destination: Optional[str] = None,
    limit: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RouteHistory)

    if source:
        stmt = stmt.where(RouteHistory.source == source)
    if destination:
        stmt = stmt.where(RouteHistory.destination == destination)
    if date_from:
        stmt = stmt.where(RouteHistory.created_at >= date_from)
    if date_to:
        stmt = stmt.where(RouteHistory.created_at <= date_to)

    if limit is not None:
        if limit <= 0:
            return JSONResponse(status_code=400, content={"error": "limit must be positive"})
        stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    records = res.scalars().all()

    response = []
    for row in records:
        response.append({
            "id": row.id,
            "source": row.source,
            "destination": row.destination,
            "total_latency": row.total_latency,
            "path": row.path,
            "created_at": row.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return response



@app.get("/nodes", status_code=200)
async def get_all_nodes(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Node))
    nodes = res.scalars().all()
    return [{"id": n.id, "name": n.name} for n in nodes]


@app.get("/edges", status_code=200)
async def get_all_edges(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Edge))
    edges = res.scalars().all()
    return [
        {"id": e.id, "source": e.source, "destination": e.destination, "latency": e.latency}
        for e in edges
    ]


@app.delete("/nodes/{id}", status_code=200)
async def remove_node(id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Node).where(Node.id == id))
    node = res.scalar_one_or_none()
    if not node:
        return JSONResponse(status_code=404, content={"error": "Node not found"})

    await db.execute(
        delete(Edge).where(or_(Edge.source == node.name, Edge.destination == node.name))
    )

    await db.delete(node)
    await db.commit()
    return {"message": f"Node {node.name} and its connected edges deleted"}


@app.delete("/edges/{id}", status_code=200)
async def remove_edge(id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Edge).where(Edge.id == id))
    edge = res.scalar_one_or_none()
    if not edge:
        return JSONResponse(status_code=404, content={"error": "Edge not found"})

    await db.delete(edge)
    await db.commit()
    return {"message": "Edge deleted"}