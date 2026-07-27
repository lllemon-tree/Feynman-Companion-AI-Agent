from typing import Literal, Optional

from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    chunk_id: str
    page_no: int
    text: str
    source: Literal["fixed", "rag"] = "rag"
    score: Optional[float] = None
