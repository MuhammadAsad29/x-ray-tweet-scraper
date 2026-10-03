import logging
import os
import uuid
from typing import Optional
from config.settings import get_settings
from src.nlu.models import ScrapeRequest
from src.nlu.local_nlu_fallback import LocalNLUParser

logger = logging.getLogger(__name__)


class DialogflowNLUClient:
    """Dialogflow CX / ES client for intent and parameter detection with local fallback."""

    def __init__(self):
        self.settings = get_settings()
        self.edition = self.settings.DIALOGFLOW_EDITION.lower()
        self.session_id = str(uuid.uuid4())

    def parse_user_intent(self, text: str) -> ScrapeRequest:
        """Processes user input using Dialogflow CX/ES or falls back to local NLU parser."""
        if self.edition == "cx" and self._has_cx_credentials():
            try:
                return self._detect_intent_cx(text)
            except Exception as e:
                logger.warning(f"Dialogflow CX error: {e}. Falling back to Local NLU parser.")
                return LocalNLUParser.parse_prompt(text)

        elif self.edition == "es" and self._has_es_credentials():
            try:
                return self._detect_intent_es(text)
            except Exception as e:
                logger.warning(f"Dialogflow ES error: {e}. Falling back to Local NLU parser.")
                return LocalNLUParser.parse_prompt(text)

        # Default to local rule-based NLU
        return LocalNLUParser.parse_prompt(text)

    def _has_cx_credentials(self) -> bool:
        return bool(
            self.settings.DIALOGFLOW_PROJECT_ID
            and self.settings.DIALOGFLOW_AGENT_ID
            and (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or self.settings.GOOGLE_APPLICATION_CREDENTIALS)
        )

    def _has_es_credentials(self) -> bool:
        return bool(
            self.settings.DIALOGFLOW_PROJECT_ID
            and (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or self.settings.GOOGLE_APPLICATION_CREDENTIALS)
        )

    def _detect_intent_cx(self, text: str) -> ScrapeRequest:
        """Calls Dialogflow CX API for intent and parameter detection."""
        from google.cloud.dialogflowcx_v3.services.sessions import SessionsClient
        from google.cloud.dialogflowcx_v3.types import DetectIntentRequest, QueryInput, TextInput

        client_options = None
        if self.settings.DIALOGFLOW_LOCATION != "global":
            api_endpoint = f"{self.settings.DIALOGFLOW_LOCATION}-dialogflow.googleapis.com"
            client_options = {"api_endpoint": api_endpoint}

        client = SessionsClient(client_options=client_options)
        session_path = (
            f"projects/{self.settings.DIALOGFLOW_PROJECT_ID}/"
            f"locations/{self.settings.DIALOGFLOW_LOCATION}/"
            f"agents/{self.settings.DIALOGFLOW_AGENT_ID}/"
            f"sessions/{self.session_id}"
        )

        text_input = TextInput(text=text)
        query_input = QueryInput(text=text_input, language_code=self.settings.DIALOGFLOW_LANGUAGE_CODE)
        request = DetectIntentRequest(session=session_path, query_input=query_input)

        response = client.detect_intent(request=request)
        query_result = response.query_result
        params = query_result.parameters

        # Extract structured fields from CX response parameters
        query = str(params.get("hashtag") or params.get("query") or text)
        since = str(params.get("start_date")) if params.get("start_date") else None
        until = str(params.get("end_date")) if params.get("end_date") else None
        limit = int(params.get("limit", 50))

        return ScrapeRequest(
            query=query,
            since=since,
            until=until,
            limit=limit,
            language=self.settings.DIALOGFLOW_LANGUAGE_CODE,
            filter_retweets=True
        )

    def _detect_intent_es(self, text: str) -> ScrapeRequest:
        """Calls Dialogflow ES API for intent and parameter detection."""
        from google.cloud import dialogflow_v2 as dialogflow

        session_client = dialogflow.SessionsClient()
        session = session_client.session_path(self.settings.DIALOGFLOW_PROJECT_ID, self.session_id)

        text_input = dialogflow.TextInput(text=text, language_code=self.settings.DIALOGFLOW_LANGUAGE_CODE)
        query_input = dialogflow.QueryInput(text=text_input)

        response = session_client.detect_intent(
            request={"session": session, "query_input": query_input}
        )
        fields = response.query_result.parameters.fields

        query = fields["hashtag"].string_value if "hashtag" in fields else text
        since = fields["start_date"].string_value if "start_date" in fields else None
        until = fields["end_date"].string_value if "end_date" in fields else None
        limit = int(fields["limit"].number_value) if "limit" in fields else 50

        return ScrapeRequest(
            query=query,
            since=since,
            until=until,
            limit=limit,
            language=self.settings.DIALOGFLOW_LANGUAGE_CODE,
            filter_retweets=True
        )
