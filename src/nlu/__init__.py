"""NLU package for parsing natural language queries into scraping parameters."""
from src.nlu.models import ScrapeRequest
from src.nlu.dialogflow_client import DialogflowNLUClient
from src.nlu.local_nlu_fallback import LocalNLUParser

__all__ = ["ScrapeRequest", "DialogflowNLUClient", "LocalNLUParser"]
