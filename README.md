# deepaudio API

Backend API for generating personalized children's stories with text-to-speech audio.

## Getting Started

```bash
docker compose up -d
# API: http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

```bash
# Create tables and insert sample data
docker compose exec web python scripts/seed.py

# Run tests
docker compose exec web python -m pytest tests/ -v
```

---

## Authentication

All endpoints except login require a JWT Bearer token.

```
Authorization: Bearer <access_token>
```

Obtain a token via `POST /api/v1/auth/login`. Tokens expire after 24 hours.

---

## Endpoints

### Auth

#### `POST /api/v1/auth/login`
Authenticate with email and password and receive a JWT token.

**Request**
```json
{
  "email": "alice@example.com",
  "password": "password123"
}
```

**Response** `200`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors**
| Status | Description |
|--------|-------------|
| `401` | Invalid email or password |

---

#### `POST /api/v1/auth/logout`
Log out. The client is responsible for discarding the token.

**Response** `200`
```json
{ "message": "Successfully logged out" }
```

---

### Children

#### `GET /api/v1/children/`
Returns the list of children belonging to the authenticated user.

**Response** `200`
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "name": "Emma",
    "age": 5,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### Stories

Manages completed stories and the story generation pipeline.

#### Story Generation Flow

```
POST /stories/
  → receive draft_id, abstract generation starts in background

GET /stories/in_progress  (poll)
  → status: generating_abstract  → wait
  → status: abstract_ready       → fetch candidates via GET /{draft_id}/abstracts

GET /stories/{draft_id}/abstracts
  → receive list of abstract candidates

POST /stories/{draft_id}/select_abstract
  → user selects a candidate

POST /stories/{draft_id}/generate_story
  → story text and audio generation starts in background

GET /stories/in_progress  (poll)
  → status: generating_text   → wait
  → status: generating_audio  → wait
  → 404                       → generation complete

GET /stories/  → list of completed stories
```

---

#### `POST /api/v1/stories/`
Starts story generation. Creates a StoryDraft and begins abstract generation in the background.

**Request**
```json
{
  "child_id": "uuid",
  "theme": "space adventure"
}
```

**Response** `201`
```json
{
  "draft_id": "uuid",
  "status": "generating_abstract"
}
```

**Errors**
| Status | Description |
|--------|-------------|
| `401` | Unauthorized |
| `422` | Validation error |

---

#### `GET /api/v1/stories/in_progress`
Returns the `draft_id` and current status of the in-progress story.

**Response** `200`
```json
{
  "draft_id": "uuid",
  "status": "abstract_ready"
}
```

**Status values**

| status | Description |
|--------|-------------|
| `generating_abstract` | Generating abstract candidates |
| `abstract_ready` | Waiting for user to select an abstract |
| `generating_text` | Generating story text |
| `generating_audio` | Generating audio |

**Errors**
| Status | Description |
|--------|-------------|
| `404` | No story in progress |

---

#### `GET /api/v1/stories/{draft_id}/abstracts`
Returns the list of generated abstract candidates. Returns `202` while still generating.

**Response** `200`
```json
[
  "A brave girl joins a friendly robot captain to collect lost stars.",
  "Emma discovers a spaceship and goes on a midnight mission.",
  "A young explorer teams up with alien friends."
]
```

**Errors**
| Status | Description |
|--------|-------------|
| `202` | Still generating — retry later |
| `404` | Draft not found |

---

#### `POST /api/v1/stories/{draft_id}/select_abstract`
Saves the user-selected abstract.

**Request**
```json
{
  "abstract": "A brave girl joins a friendly robot captain to collect lost stars."
}
```

**Response** `200`
```json
{
  "draft_id": "uuid",
  "status": "generating_text"
}
```

**Errors**
| Status | Description |
|--------|-------------|
| `404` | Draft not found |
| `409` | Abstracts are not ready yet |

---

#### `POST /api/v1/stories/{draft_id}/generate_story`
Triggers story text and audio generation in the background. When complete, a Story record is created and the draft is deleted.

**Response** `202`
```json
{
  "draft_id": "uuid",
  "status": "generating_text"
}
```

**Errors**
| Status | Description |
|--------|-------------|
| `404` | Draft not found |
| `409` | Abstract has not been selected yet |

---

#### `GET /api/v1/stories/`
Returns a paginated list of completed stories.

**Query Parameters**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `20` | Number of results (1–100) |
| `offset` | int | `0` | Number of results to skip |

**Response** `200`
```json
{
  "items": [
    {
      "id": "uuid",
      "child_id": "uuid",
      "theme": "space adventure",
      "title": "Emma and the Star Pirates",
      "abstracts": ["candidate A", "candidate B", "candidate C"],
      "abstract": "selected abstract",
      "content": "Once upon a time...",
      "audio_url": "https://storage.example.com/audio/xxx.mp3",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

#### `GET /api/v1/stories/{story_id}`
Returns a single completed story by ID.

**Response** `200` — same schema as `items[n]` in `GET /api/v1/stories/`

**Errors**
| Status | Description |
|--------|-------------|
| `404` | Story not found |

---

#### `GET /api/v1/stories/{story_id}/audio`
Returns the audio file for a completed story.

**Response** `200` — binary audio data (`audio/mpeg` or equivalent)

**Errors**
| Status | Description |
|--------|-------------|
| `404` | Story not found or audio not yet generated |
| `502` | Failed to connect to TTS service |

---

#### `DELETE /api/v1/stories/{story_id}`
Soft-deletes a story. The record is retained in the database but hidden from all user-facing queries.

**Response** `204` No Content

**Errors**
| Status | Description |
|--------|-------------|
| `404` | Story not found |

---

## Data Models

### StoryDraft (temporary, in-progress data)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Draft ID |
| `child_id` | UUID | Child ID (1:1) |
| `theme` | string | Story theme |
| `abstracts` | string[] \| null | Generated abstract candidates |
| `selected_abstract` | string \| null | Abstract chosen by the user |
| `title` | string \| null | Generated title |
| `generated_text` | string \| null | Generated story body |

**Status is inferred from which fields are populated:**

```
abstracts = null           → generating_abstract
abstracts set              → abstract_ready
selected_abstract set      → generating_text
generated_text set         → generating_audio
(draft deleted)            → completed
```

### Story (permanent, completed data)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Story ID |
| `child_id` | UUID | Child ID |
| `theme` | string | Story theme |
| `title` | string \| null | Generated title |
| `abstracts` | string[] \| null | All generated abstract candidates |
| `abstract` | string \| null | The selected abstract |
| `content` | string \| null | Story body text |
| `audio_url` | string \| null | Audio file URL |
| `is_deleted` | bool | Soft-delete flag |
