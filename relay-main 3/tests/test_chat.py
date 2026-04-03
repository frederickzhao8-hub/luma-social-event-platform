from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from luma.api.deps import get_current_user_id
from luma.api.routes import chat as chat_routes
from luma.main import app
from luma.schemas.chat import ChatMessageRead, ChatResponse, ChatUsage
from luma.services.ai_service import ChatAIError, ChatPersistenceError


class FakeAIService:
    def __init__(
        self,
        *,
        response: ChatResponse | None = None,
        chat_error: Exception | None = None,
        history: list[ChatMessageRead] | None = None,
    ) -> None:
        self.response = response
        self.chat_error = chat_error
        self.history = history or []

    async def chat(self, *, user_id: int, query: str) -> ChatResponse:
        if self.chat_error is not None:
            raise self.chat_error
        assert user_id == 1
        assert query == "music this weekend"
        assert self.response is not None
        return self.response

    async def get_history(self, user_id: int, limit: int = 10) -> list[ChatMessageRead]:
        assert user_id == 1
        assert limit == 10
        return self.history

    async def clear_history(self, user_id: int) -> int:
        assert user_id == 1
        return 0


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def _override_auth(user_id: int) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def _override_service(service: FakeAIService) -> None:
    app.dependency_overrides[chat_routes._get_service] = lambda: service


def test_chat_returns_usage_and_costs() -> None:
    _override_auth(1)
    _override_service(
        FakeAIService(
            response=ChatResponse(
                reply="Try the jazz concert downtown.",
                timestamp=datetime(2026, 3, 30, 12, 0, tzinfo=UTC),
                usage=ChatUsage(
                    model="gpt-4o-mini",
                    input_tokens=512,
                    output_tokens=128,
                    total_tokens=640,
                    estimated_input_cost_usd=0.0000768,
                    estimated_output_cost_usd=0.0000768,
                    estimated_total_cost_usd=0.0001536,
                ),
            )
        )
    )

    client = TestClient(app)
    response = client.post("/api/v1/chat", json={"query": "music this weekend"})

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "Try the jazz concert downtown."
    assert data["usage"]["model"] == "gpt-4o-mini"
    assert data["usage"]["input_tokens"] == 512
    assert data["usage"]["output_tokens"] == 128
    assert data["usage"]["total_tokens"] == 640
    assert data["usage"]["estimated_total_cost_usd"] == 0.0001536


def test_chat_returns_504_on_provider_error() -> None:
    _override_auth(1)
    _override_service(FakeAIService(chat_error=ChatAIError("OpenAI request failed.")))

    client = TestClient(app)
    response = client.post("/api/v1/chat", json={"query": "music this weekend"})

    assert response.status_code == 504
    assert response.json()["detail"] == "OpenAI request failed."


def test_chat_returns_503_on_persistence_error() -> None:
    _override_auth(1)
    _override_service(FakeAIService(chat_error=ChatPersistenceError("Failed to save chat messages.")))

    client = TestClient(app)
    response = client.post("/api/v1/chat", json={"query": "music this weekend"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Failed to save chat messages."
