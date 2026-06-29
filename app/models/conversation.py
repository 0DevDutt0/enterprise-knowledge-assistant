# app/models/conversation.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel, frozen=True):
    """A single completed question/answer exchange in a conversation.

    Passed from the client on subsequent requests so the LLM can resolve
    pronouns and follow-up questions against prior context. Only successful
    (non-refusal) turns should be included -- refusals carry no useful context.
    """

    query: str = Field(..., min_length=1, description='The user question.')
    answer: str = Field(..., min_length=1, description='The assistant response text.')
