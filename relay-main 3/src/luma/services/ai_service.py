import json
import logging
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from luma.core.config import settings
from luma.db.models.chat import ChatRole
from luma.repositories.chat_repository import ChatRepository
from luma.repositories.event_repository import EventRepository
from luma.schemas.chat import ChatResponse, ChatUsage

try:
    from openai import APITimeoutError, AsyncOpenAI, OpenAIError
except ModuleNotFoundError:  # pragma: no cover - runtime safety fallback
    APITimeoutError = TimeoutError  # type: ignore[assignment]
    AsyncOpenAI = None

    class OpenAIError(Exception):
        pass


class ChatPersistenceError(Exception):
    """Raised when chat history cannot be read or saved."""


class ChatAIError(Exception):
    """Raised when AI provider call fails."""


logger = logging.getLogger(__name__)


class AIService:
    """Application service for AI chat with DB-backed memory."""

    def __init__(self, chat_repository: ChatRepository, event_repository: EventRepository) -> None:
        self.chat_repository = chat_repository
        self.event_repository = event_repository
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
            if AsyncOpenAI
            else None
        )

    async def get_history(self, user_id: int, limit: int = 10):
        try:
            return await self.chat_repository.get_history(user_id=user_id, limit=limit)
        except SQLAlchemyError as exc:
            raise ChatPersistenceError("Failed to load chat history.") from exc

    async def clear_history(self, user_id: int) -> int:
        try:
            return await self.chat_repository.clear_history(user_id=user_id)
        except SQLAlchemyError as exc:
            raise ChatPersistenceError("Failed to clear chat history.") from exc

    async def chat(self, *, user_id: int, query: str) -> ChatResponse:
        if not self.client:
            raise ChatAIError("OpenAI SDK is not installed in current environment.")
        if not settings.openai_api_key:
            raise ChatAIError("OpenAI API key is not configured.")

        try:
            history = await self.chat_repository.get_history(user_id=user_id, limit=10)
            events = await self.event_repository.list_latest_events(limit=50)
        except SQLAlchemyError as exc:
            raise ChatPersistenceError("Failed to read context data from database.") from exc

        event_context = self._events_to_context(events)
        messages = self._build_messages(query=query, history=history, event_context=event_context)

        try:
            completion = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
            )
        except APITimeoutError as exc:
            raise ChatAIError("OpenAI request timed out.") from exc
        except OpenAIError as exc:
            raise ChatAIError("OpenAI request failed.") from exc

        reply = (completion.choices[0].message.content or "").strip()
        if not reply:
            reply = "Sorry, I couldn't generate a valid response right now. Please try again later."

        timestamp = datetime.now(UTC)
        usage = self._build_usage(completion)

        try:
            await self.chat_repository.save_message(
                user_id=user_id, role=ChatRole.USER.value, content=query
            )
            await self.chat_repository.save_message(
                user_id=user_id, role=ChatRole.ASSISTANT.value, content=reply
            )
        except SQLAlchemyError as exc:
            raise ChatPersistenceError("Failed to save chat messages.") from exc

        if usage is not None:
            logger.info(
                "OpenAI chat usage | user_id=%s model=%s input_tokens=%s output_tokens=%s "
                "total_tokens=%s estimated_total_cost_usd=%.8f",
                user_id,
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
                usage.estimated_total_cost_usd,
            )

        return ChatResponse(reply=reply, timestamp=timestamp, usage=usage)

    def _events_to_context(self, events) -> str:
        payload = [
            {
                "id": str(event.id),
                "title": event.title,
                "description": event.description,
                "category": event.category,
                "date": event.date,
                "time": event.time,
                "address": event.address,
                "tags": event.tags,
                "organizerName": event.organizer_name,
                "organizerEmail": event.organizer_email,
                "participantLimit": event.participant_limit,
                "currentParticipants": event.current_participants,
                "createdAt": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ]
        return json.dumps(payload, ensure_ascii=False)

    def _build_messages(self, *, query: str, history, event_context: str) -> list[dict[str, str]]:
        system_prompt = (
            "You are the event assistant for the Luma platform. Your answers must be based on "
            "the system-provided event data and the user's question. If data is insufficient, "
            "state that clearly. Here is the activity JSON from the database:\n"
            f"{event_context}"
        )
        ordered_history = list(reversed(history))
        history_messages = [
            {"role": message.role, "content": message.content}
            for message in ordered_history
            if message.role in {ChatRole.USER.value, ChatRole.ASSISTANT.value}
        ]
        return [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": query},
        ]

    def _build_usage(self, completion) -> ChatUsage | None:
        usage = getattr(completion, "usage", None)
        if usage is None:
            return None

        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(
            getattr(usage, "total_tokens", input_tokens + output_tokens) or input_tokens + output_tokens
        )

        estimated_input_cost_usd = round(
            input_tokens * settings.openai_input_cost_per_million_tokens / 1_000_000,
            8,
        )
        estimated_output_cost_usd = round(
            output_tokens * settings.openai_output_cost_per_million_tokens / 1_000_000,
            8,
        )
        estimated_total_cost_usd = round(
            estimated_input_cost_usd + estimated_output_cost_usd,
            8,
        )

        return ChatUsage(
            model=settings.openai_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_input_cost_usd=estimated_input_cost_usd,
            estimated_output_cost_usd=estimated_output_cost_usd,
            estimated_total_cost_usd=estimated_total_cost_usd,
        )
