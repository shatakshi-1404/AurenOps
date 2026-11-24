from fastapi import APIRouter, Depends

from app.api.v1 import (admin, agents, approvals, audit, auth, dashboard, documents, integrations,
                        operations, reports, ws)
from app.core.deps import rate_limit

api = APIRouter(prefix="/api/v1")
for m in (auth, operations, approvals, agents, documents, integrations, reports, audit, dashboard, admin):
    api.include_router(m.router, dependencies=[Depends(rate_limit)])
api.include_router(ws.router)
