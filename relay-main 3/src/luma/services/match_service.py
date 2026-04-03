from luma.cache import match_pool
from luma.repositories.event_repository import EventRepository
from luma.repositories.user_repository import UserRepository
from luma.schemas.event import Location, MapEventRead
from luma.schemas.match import MatchStatusResponse
from luma.schemas.user import UserRead


class MatchService:
    def __init__(self, user_repo: UserRepository, event_repo: EventRepository) -> None:
        self.user_repo = user_repo
        self.event_repo = event_repo

    async def activate(self, user_id: int, lat: float, lng: float) -> MatchStatusResponse:
        await match_pool.add_to_pool(user_id, lat, lng)
        result = await self._find_and_create_match(user_id, lat, lng)
        if result:
            return result
        return MatchStatusResponse(status="waiting", expires_in=20)

    async def get_status(self, user_id: int) -> MatchStatusResponse:
        # 1. Check if already matched
        result_data = await match_pool.get_result(user_id)
        if result_data:
            suggested = (
                MapEventRead.model_validate(result_data["suggested_event"])
                if result_data.get("suggested_event")
                else None
            )
            return MatchStatusResponse(
                status="matched",
                matched_user=UserRead.model_validate(result_data["matched_user"]),
                suggested_event=suggested,
            )

        # 2. Check if still waiting
        ttl = await match_pool.get_meta_ttl(user_id)
        if ttl > 0:
            return MatchStatusResponse(status="waiting", expires_in=ttl)

        # 3. Neither → timed out
        return MatchStatusResponse(status="timeout")

    async def cancel(self, user_id: int) -> None:
        await match_pool.remove_from_pool(user_id)

    async def _find_and_create_match(
        self, user_id: int, lat: float, lng: float
    ) -> MatchStatusResponse | None:
        candidates = await match_pool.find_nearby(user_id)
        if not candidates:
            return None

        other_id = candidates[0]

        # Acquire dedup lock — only one side proceeds
        if not await match_pool.acquire_lock(user_id, other_id):
            return None

        current_user = await self.user_repo.get_by_id(user_id)
        other_user = await self.user_repo.get_by_id(other_id)
        if not current_user or not other_user:
            return None

        # Find nearest event to midpoint of both users
        other_pos = await match_pool.get_position(other_id)
        if other_pos:
            other_lat, other_lng = other_pos
            mid_lat = (lat + other_lat) / 2
            mid_lng = (lng + other_lng) / 2
        else:
            mid_lat, mid_lng = lat, lng

        suggested_event = await self._suggest_event(mid_lat, mid_lng)

        current_user_data = UserRead.model_validate(current_user).model_dump()
        other_user_data = UserRead.model_validate(other_user).model_dump()
        suggested_event_data = (
            suggested_event.model_dump(mode="json") if suggested_event else None
        )

        # Write results before removing from pool (prevents false timeout on poll)
        await match_pool.save_result(
            other_id,
            {"matched_user": current_user_data, "suggested_event": suggested_event_data},
        )
        await match_pool.save_result(
            user_id,
            {"matched_user": other_user_data, "suggested_event": suggested_event_data},
        )

        # Now remove both from pool
        await match_pool.remove_from_pool(user_id)
        await match_pool.remove_from_pool(other_id)

        return MatchStatusResponse(
            status="matched",
            matched_user=UserRead.model_validate(other_user),
            suggested_event=suggested_event,
        )

    async def _suggest_event(self, lat: float, lng: float) -> MapEventRead | None:
        events = await self.event_repo.find_nearest(lat, lng)
        if not events:
            return None
        event = events[0]
        return MapEventRead.model_validate(
            {
                "id": event.id,
                "title": event.title,
                "category": event.category,
                "date": event.date,
                "time": event.time,
                "address": event.address,
                "location": Location(lat=event.latitude, lng=event.longitude),
            }
        )
