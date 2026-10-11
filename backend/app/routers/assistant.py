"""Global assistant: ask Gemini anything about the whole network."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...ai import gemini as gemini_mod
from ...ai import global_context as global_mod
from ..deps import store_dep

router = APIRouter(prefix="/assistant", tags=["assistant"])


class Turn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(max_length=4000)


class AskAllBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=12)


@router.post("/ask")
def ask(body: AskAllBody, store=Depends(store_dep)) -> dict:
    """Answer a free-form question using all internal data plus live weather/news."""
    context, sources, articles = global_mod.build_global_context(store, body.question)
    answer = gemini_mod.answer_global(context, body.question, [t.model_dump() for t in body.history])
    return {**answer, "sources": sources, "articles": articles}
