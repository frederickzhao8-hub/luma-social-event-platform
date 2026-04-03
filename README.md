# LUMA

LUMA is a full-stack event discovery and social matching platform built with React, FastAPI, PostgreSQL, Redis, and OpenAI.

The project supports event browsing, search and filtering, map-based discovery, authentication, event posting, bookmarks, event registration, location-based matching, and an AI-powered chat backend for event assistance.

## Overview

This repository currently contains two app folders:

- `frontend/`: frontend application
- `luma/`: backend API

The frontend provides the product experience for end users, while the backend handles authentication, event data, registrations, chat persistence, matchmaking, and AI integration.

## Features

### Frontend

- Event discovery with search, category filters, date filters, and distance filters
- Interactive event map built with Leaflet
- Event detail pages and protected event posting flow
- Bookmark system for saved events
- User authentication flow with protected routes
- "Shake to Match" interaction prototype in the explore experience
- Global chatbot UI for event suggestions
- User footprint map view based on local check-in history

### Backend

- FastAPI REST API with layered architecture (`routes -> services -> repositories`)
- User signup, login, logout, and session-based auth
- Event CRUD endpoints
- Event registration and cancellation endpoints
- Map discovery endpoint with viewport bounding-box filtering
- Redis-backed location matching pool
- Chat history persistence in PostgreSQL
- OpenAI-backed chat service with token and estimated cost reporting
- Automated tests covering auth, health, map discovery, chat, registration, and matching

## Tech Stack

### Frontend

- React 18
- TypeScript
- Vite
- React Router
- Tailwind CSS
- Leaflet / React Leaflet
- Radix UI components

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- Redis
- Alembic
- OpenAI Python SDK
- Pytest

## Repository Structure

```text
.
├── frontend/                # Frontend app
│   ├── src/app/
│   │   ├── components/
│   │   ├── context/
│   │   ├── data/
│   │   ├── lib/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
├── luma/                    # Backend app
│   ├── src/luma/
│   │   ├── api/routes/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── db/models/
│   │   ├── schemas/
│   │   ├── cache/
│   │   └── core/
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── docker-compose.yml
└── README.md
```

## Current Product Flow

- Users can browse events from the home page and explore page
- Users can search and filter events by category, date, time, and distance
- Users can view events on a map and inspect location details
- Authenticated users can post new events
- Users can register or unregister for events through the backend API
- Users can open a chatbot experience for event suggestions
- Users can activate location-based matching through the backend matching service

## AI Integration

The repository includes a real OpenAI-backed backend chat service in `luma/src/luma/services/ai_service.py`.

Current AI-related behavior is split into two layers:

- Backend: real OpenAI integration with persisted chat history and usage / cost reporting
- Frontend chatbot UI: currently implemented as a local rules-based event suggestion assistant

This means the backend AI service is implemented, but the current frontend floating chatbot has not yet been fully wired to the backend chat endpoint.

## API Summary

Backend routes currently include:

- `/api/v1/health`
- `/api/v1/auth`
- `/api/v1/users`
- `/api/v1/events`
- `/api/v1/match`
- `/api/v1/chat`

Notable capabilities:

- Event list and detail retrieval
- Event creation, update, deletion
- Event registration / unregistration
- Map viewport event queries
- Match activation / status / cancellation
- AI chat requests with usage metadata

## Local Development

### 1. Frontend

```bash
cd "frontend"
npm install --legacy-peer-deps
npm run dev
```

Default local URL:

- `http://localhost:3000`

Note:

- `vite.config.ts` currently proxies `/api` to a deployed backend by default.
- If you want the frontend to hit your local backend instead, you can run with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0
```

### 2. Backend

Recommended stack:

- Python 3.12
- PostgreSQL
- Redis

Example setup:

```bash
cd "luma"
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest pytest-asyncio httpx
alembic upgrade head
uvicorn luma.main:app --reload
```

Default local URL:

- `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Environment Variables

Important backend environment variables:

```env
DATABASE_URL=
REDIS_URL=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=20.0
OPENAI_INPUT_COST_PER_MILLION_TOKENS=0.15
OPENAI_OUTPUT_COST_PER_MILLION_TOKENS=0.60
```

## Testing

Backend tests live in `luma/tests/` and currently cover:

- auth
- health
- map discovery
- chat
- event registration
- location matching

## Implementation Notes

- The backend uses session cookies stored in Redis for authentication.
- Chat history is persisted in PostgreSQL and the OpenAI chat response now includes token usage and estimated cost information.
- Matching uses Redis as a short-lived geo pool for nearby-user discovery.
- The frontend includes a number of experimental or extra pages that are not all currently mounted in the main route tree.

## Known Gaps / Current Status

- The backend OpenAI chat service is implemented, but the frontend chatbot is still using local matching logic instead of the backend `/api/v1/chat` endpoint.
- The frontend "Shake to Match" experience exists, while backend matching currently exposes `/match/activate`, `/match/status`, and `/match` cancellation endpoints.
- This repository reflects an actively evolving course project rather than a fully polished production deployment.
