import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from services.api.auth import rate_limit, verify_token

router = APIRouter()

_submissions: dict[str, dict] = {}


class AssessmentSubmit(BaseModel):
    knowledge_id: Optional[str] = None
    answers: list[dict] = []
    user_id: Optional[str] = None


@router.post("/assessment/submit")
@rate_limit()
async def submit_assessment(request: Request, body: AssessmentSubmit):
    verify_token(request)
    assessment_id = str(uuid.uuid4())
    _submissions[assessment_id] = body.model_dump()
    return {"status": "received", "assessment_id": assessment_id}
