from pydantic import BaseModel
from typing import List, Optional

class AnalysisRequest(BaseModel):
    # We don't strictly need a body for file upload, 
    # but if we had options (e.g. "strict mode"), they would go here.
    pass

class Suggestion(BaseModel):
    original_text: str
    issue_type: str  # "grammar", "spelling", "clarity", "other"
    description: str
    suggestion: str

class AnalysisResult(BaseModel):
    filename: str
    suggestions: List[Suggestion]
    general_comments: Optional[str] = None
