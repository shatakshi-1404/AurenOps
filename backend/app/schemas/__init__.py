import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    org_name: str = Field(min_length=2, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    org_id: Optional[uuid.UUID] = None


class InviteIn(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "operator"


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class SwitchOrgIn(BaseModel):
    org_id: uuid.UUID


class OperationIn(BaseModel):
    request: str = Field(min_length=5, max_length=2000)


class DraftEdit(BaseModel):
    email_id: uuid.UUID
    subject: Optional[str] = Field(None, max_length=300)
    body: Optional[str] = Field(None, max_length=8000)


class EditApprovalIn(BaseModel):
    drafts: list[DraftEdit]


class ApproveIn(BaseModel):
    payload_hash: str  # hash the reviewer saw; stale hash => 409
    email_ids: Optional[list[uuid.UUID]] = None  # approve-selected
    note: Optional[str] = None


class RejectIn(BaseModel):
    note: Optional[str] = None


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=20)
    category: Optional[str] = None


class IntegrationIn(BaseModel):
    kind: str
    name: str
    provider: str = "mock"
    config: dict = {}


class RotateIn(BaseModel):
    config: dict


class ReportIn(BaseModel):
    kind: str = "collection"


class RoleUpdateIn(BaseModel):
    role: str


class PolicyUpdateIn(BaseModel):
    mode: str  # auto | approval | restricted
    risk: Optional[str] = None
    approver_min_role: Optional[str] = None
