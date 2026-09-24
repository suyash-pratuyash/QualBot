# QualBot API Contract v1.0

**Status:** Frozen v1.0 contract  
**REST base:** `/api/v1`  
**WebSocket base:** `/ws/v1`  
**Payload format:** JSON (WebSocket frames also carry JSON)  
**Authority:** The backend owns persistence, BANT state, scoring, qualification, and routing. Gemini interprets language; it does not decide scores or actions.

This document is the local implementation reference. It records the Day 2 endpoint shapes, examples, and rules, together with the JWT admin-authentication decision made before Phase 0. It describes the API; it does not imply that these endpoints or business features have been implemented.

## 1. Shared conventions

### Success payloads

Successful REST responses are JSON objects returned directly, without a `data` wrapper. Paginated collections use `items` and `pagination`.

### Error payload

Every REST error uses this envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request.",
    "details": null
  }
}
```

`details` is either `null` or a JSON value with safe field-level information. Do not expose stack traces, credentials, provider secrets, or raw model output.

### Common HTTP status codes

| Status | Meaning |
|---|---|
| `200` | Request completed; includes recorded action outcomes |
| `201` | Resource created |
| `400` | Malformed or otherwise invalid request |
| `401` | Missing or invalid authentication / invalid login credentials |
| `403` | Authenticated principal is not allowed to perform the operation |
| `404` | Requested resource does not exist or is not accessible to the caller |
| `409` | Conflict with current resource or action state |
| `422` | Well-formed JSON/query whose values fail schema validation |
| `500` | Unexpected internal error |
| `502` | An external service failed or could not confirm its outcome |

Authentication failures and validation failures use the same error envelope. FastAPI's framework-default error shape must be normalized to this contract when endpoint implementation begins.

### Common validation and data rules

- IDs are opaque strings. Examples use `conv_001`, `lead_001`, and `admin_001` for readability.
- Timestamps are ISO 8601 UTC strings, such as `2026-09-24T12:30:00Z`.
- Scores are integers from 0 through 100. BANT confidence values are numbers from 0.0 through 1.0. BANT completion is an integer from 0 through 100 and is distinct from score.
- Missing BANT information is represented with `value: null` and `confidence: null`; unknown information must not be fabricated.
- User messages contain 1–2000 characters. Pagination uses `page >= 1` and `1 <= limit <= 100`; defaults are page 1 and limit 20.
- Client-supplied scores, qualification outcomes, BANT state, and routing decisions are never authoritative.

## 2. Authentication and authorization

Admin authentication is JWT-based and implemented by FastAPI. Passwords are stored only as standard one-way password hashes; plaintext passwords are never stored.

| API | Authentication |
|---|---|
| `POST /api/v1/auth/login` | Public |
| `GET /api/v1/auth/me` | Admin bearer JWT required |
| Conversation create/read and conversation WebSocket | Public widget access; conversation ID scopes access to that conversation |
| Leads, analytics, and action endpoints | Admin bearer JWT required |
| `GET /api/v1/health` | Public |

Protected requests send `Authorization: Bearer <access_token>`. Public widget access cannot list leads, inspect other conversations, view analytics, modify leads, or trigger arbitrary actions.

### `POST /api/v1/auth/login`

Authenticates an admin and issues a one-hour access token.

**Request:** `application/json`; public.

```json
{
  "email": "admin@example.com",
  "password": "correct-horse-battery-staple"
}
```

`email` is required and must be a valid email address. `password` is required and non-empty.

**Response — `200`:**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Invalid credentials return `401` with code `INVALID_CREDENTIALS`. Invalid request fields return `422 VALIDATION_ERROR`.

### `GET /api/v1/auth/me`

Returns the identity represented by the bearer token. No request body.

**Response — `200`:**

```json
{
  "id": "admin_001",
  "email": "admin@example.com",
  "role": "admin"
}
```

Missing, expired, or invalid token returns `401` (`AUTHENTICATION_REQUIRED` or `INVALID_TOKEN`).

## 3. Conversation API

### `POST /api/v1/conversations`

Creates a visitor conversation. Public widget endpoint.

**Request:**

```json
{
  "visitor_id": "visitor_abc123",
  "page_url": "https://example.com/pricing"
}
```

`visitor_id` is required, a string of 1–100 characters. `page_url` is optional and, when present, must be a valid absolute URL.

**Response — `201`:**

```json
{
  "conversation_id": "conv_001",
  "status": "active",
  "created_at": "2026-09-24T12:30:00Z"
}
```

Validation failure returns `422 VALIDATION_ERROR`; malformed JSON returns `400 INVALID_REQUEST`.

### `GET /api/v1/conversations/{conversation_id}`

Returns the current state of the requested conversation. Public widget endpoint scoped to that conversation ID. No request body.

**Response — `200`:**

```json
{
  "conversation_id": "conv_001",
  "status": "active",
  "lead_score": 68,
  "qualification_status": "qualified",
  "bant": {
    "budget": { "value": "₹50,000", "confidence": 0.91 },
    "authority": { "value": "decision_maker", "confidence": 0.84 },
    "need": { "value": "AI chatbot for website", "confidence": 0.95 },
    "timeline": { "value": "within_1_month", "confidence": 0.88 }
  },
  "created_at": "2026-09-24T12:30:00Z",
  "updated_at": "2026-09-24T12:35:00Z"
}
```

Each BANT dimension has a nullable `value` and nullable `confidence`. Confidence, when present, is in `[0,1]`. `lead_score` is in `[0,100]`. Contract example qualification values are `unqualified`, `qualified`, and `high_intent`.

Missing or inaccessible conversation returns `404 CONVERSATION_NOT_FOUND`:

```json
{
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Conversation not found.",
    "details": null
  }
}
```

## 4. WebSocket conversation API

**Endpoint:** `/ws/v1/conversations/{conversation_id}`  
**Authentication:** Public widget access, scoped to the conversation ID.  
**Frames:** JSON objects with a required `type` string. The client sends `user_message`; the server emits the event types below. Events are sent only when applicable; the server, not the client, determines BANT, score, qualification, and booking availability.

### Client → server: `user_message`

```json
{
  "type": "user_message",
  "message": "We need an AI chatbot for our website."
}
```

`message` is required, a string of 1–2000 characters. Unknown event types or invalid payloads receive an `error` event with code `INVALID_WEBSOCKET_MESSAGE`. The server may send a `conversation_completed` event when the conversation is complete.

### Server → client events

#### `assistant_message`

```json
{
  "type": "assistant_message",
  "message": "Absolutely. Could you tell me what you want the chatbot to accomplish?"
}
```

On AI failure, send a safe fallback message and keep the conversation available; do not fabricate BANT values, scores, or routing outcomes.

#### `bant_update`

```json
{
  "type": "bant_update",
  "updated": ["need", "timeline"],
  "completion": 75
}
```

`updated` contains zero or more of `budget`, `authority`, `need`, `timeline`. `completion` is BANT completeness, integer 0–100; it is not the lead score.

#### `score_update`

```json
{
  "type": "score_update",
  "score": 72
}
```

`score` is an integer in `[0,100]`, calculated by the backend.

#### `qualification_update`

```json
{
  "type": "qualification_update",
  "status": "high_intent"
}
```

The Day 2 event example uses `unqualified`, `qualified`, and `high_intent`. Qualification is determined by backend rules.

#### `booking_available`

```json
{
  "type": "booking_available",
  "provider": "calendly",
  "url": "https://calendly.com/example/intro"
}
```

The URL is produced by the backend integration. The frontend must not construct Calendly URLs.

#### `conversation_completed`

```json
{
  "type": "conversation_completed"
}
```

#### `error`

```json
{
  "type": "error",
  "code": "AI_RESPONSE_INVALID",
  "message": "We were unable to process that message."
}
```

The client presents a user-friendly message and does not expose internal stack traces or provider details. Known internal error codes include `AI_SERVICE_ERROR`, `AI_TIMEOUT`, `AI_RESPONSE_INVALID`, and `AI_EXTRACTION_FAILED`. On model failure, a safe `assistant_message` fallback may be sent; the conversation must not be terminated or state corrupted solely because the model failed.

## 5. BANT representation

Each dimension (`budget`, `authority`, `need`, `timeline`) has this shape:

```json
{
  "value": "decision_maker",
  "confidence": 0.91
}
```

An unknown dimension is represented as:

```json
{
  "value": null,
  "confidence": null
}
```

Confidence is nullable and otherwise in `[0.0,1.0]`. The backend retains BANT across turns and does not replace supported state with absent information. No endpoint accepts client-authored BANT as authoritative.

## 6. Lead API

Qualification values used by the API examples are `unqualified`, `qualified`, and `high_intent`. Operational lead statuses are separate: `new`, `contacted`, `converted`, and `closed`.

### `GET /api/v1/leads`

Lists leads. Admin bearer JWT required. No body.

Query parameters:

| Name | Type | Required | Rules |
|---|---|---:|---|
| `page` | integer | No | Default 1; `>= 1` |
| `limit` | integer | No | Default 20; 1–100 |
| `status` | string | No | Qualification filter: `unqualified`, `qualified`, or `high_intent` |
| `min_score` | integer | No | 0–100 |
| `max_score` | integer | No | 0–100 and not less than `min_score` |

Example: `GET /api/v1/leads?page=1&limit=20&status=high_intent&min_score=70`

**Response — `200`:**

```json
{
  "items": [
    {
      "lead_id": "lead_001",
      "conversation_id": "conv_001",
      "score": 82,
      "qualification_status": "high_intent",
      "created_at": "2026-09-24T12:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 82,
    "pages": 5
  }
}
```

Invalid query values return `422 VALIDATION_ERROR`; missing/invalid admin credentials return `401`; non-admin access returns `403`.

### `GET /api/v1/leads/{lead_id}`

Returns one lead and its qualification/routing state. Admin bearer JWT required. No body.

**Response — `200`:**

```json
{
  "lead_id": "lead_001",
  "conversation_id": "conv_001",
  "score": 82,
  "qualification_status": "high_intent",
  "bant": {
    "budget": { "value": "₹50,000", "confidence": 0.91 },
    "authority": { "value": "decision_maker", "confidence": 0.84 },
    "need": { "value": "AI chatbot", "confidence": 0.95 },
    "timeline": { "value": "within_1_month", "confidence": 0.88 }
  },
  "routing": {
    "email_alert": "sent",
    "booking": "available"
  },
  "created_at": "2026-09-24T12:30:00Z",
  "updated_at": "2026-09-24T12:35:00Z"
}
```

`score` is 0–100. BANT values and confidence follow Section 5. Missing or inaccessible lead returns `404 LEAD_NOT_FOUND`; authentication failures return `401` or `403`.

### `PATCH /api/v1/leads/{lead_id}`

Updates only the operational status. Admin bearer JWT required.

**Request:**

```json
{
  "status": "contacted"
}
```

`status` is required and must be one of `new`, `contacted`, `converted`, or `closed`. The request must not contain `score`, `qualification_status`, BANT, or routing fields; calculated values remain backend-controlled.

**Response — `200`:**

```json
{
  "lead_id": "lead_001",
  "status": "contacted",
  "updated_at": "2026-09-24T12:35:00Z"
}
```

Missing lead returns `404 LEAD_NOT_FOUND`; invalid status or attempted calculated-field update returns `422 VALIDATION_ERROR`; missing/invalid token returns `401`; non-admin access returns `403`.

## 7. Analytics API

### `GET /api/v1/analytics/overview`

Returns server-calculated admin analytics. Admin bearer JWT required. No body.

**Response — `200`:**

```json
{
  "total_conversations": 1240,
  "total_leads": 486,
  "qualified_leads": 173,
  "high_intent_leads": 82,
  "average_lead_score": 61.4,
  "conversion_rate": 14.2
}
```

Counts are nonnegative integers. `average_lead_score` is a number in `[0,100]`; `conversion_rate` is a percentage in `[0,100]`. The dashboard does not calculate these business metrics. Missing/invalid admin credentials return `401`; non-admin access returns `403`.

## 8. Action API

These endpoints are for administrative manual trigger/retry, testing, or recovery. Normal qualification and automatic routing remain backend processes; the frontend does not decide whether a lead qualifies. Both endpoints require admin bearer JWT. Request body is omitted.

### `POST /api/v1/actions/{lead_id}/email-alert`

Triggers or retries the email alert for the lead.

**Recorded success — `200`:**

```json
{
  "action": "email_alert",
  "status": "success",
  "lead_id": "lead_001"
}
```

**Recorded failure — `200`:**

```json
{
  "action": "email_alert",
  "status": "failed",
  "lead_id": "lead_001"
}
```

The response reports the recorded outcome; it must not claim delivery when the provider has not confirmed it. Missing lead returns `404 LEAD_NOT_FOUND`; an action that cannot be started in the current state returns `409 ACTION_NOT_AVAILABLE`; unavailable provider or unconfirmed outcome returns `502 EMAIL_SERVICE_ERROR` using the common error envelope. Authentication failures return `401` or `403`.

### `POST /api/v1/actions/{lead_id}/booking`

Initiates or returns the booking flow for the lead.

**Response — `200`:**

```json
{
  "action": "booking",
  "status": "available",
  "provider": "calendly",
  "url": "https://calendly.com/example/intro"
}
```

The backend generates the booking URL. Missing lead returns `404 LEAD_NOT_FOUND`; unavailable booking for the lead returns `409 ACTION_NOT_AVAILABLE`; unavailable or failed booking provider returns `502 CALENDLY_ERROR` using the common error envelope. Authentication failures return `401` or `403`.

## 9. Health API

### `GET /api/v1/health`

Public, bodyless liveness check.

**Healthy response — `200`:**

```json
{
  "status": "ok"
}
```

When the application cannot serve requests, return `503` and the common error envelope. The health response does not expose secrets or internal diagnostics.

## 10. WebSocket and HTTP error codes

The common REST error codes include `VALIDATION_ERROR`, `INVALID_REQUEST`, `AUTHENTICATION_REQUIRED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS`, `CONVERSATION_NOT_FOUND`, `LEAD_NOT_FOUND`, `ACTION_NOT_AVAILABLE`, `EMAIL_SERVICE_ERROR`, `CALENDLY_ERROR`, and `INTERNAL_SERVER_ERROR`. WebSocket errors use the event schema in Section 4; AI provider codes include `AI_SERVICE_ERROR`, `AI_TIMEOUT`, `AI_RESPONSE_INVALID`, and `AI_EXTRACTION_FAILED`.

An external service failure must be recorded as a failed action or returned as an error; a requested action is not equivalent to successful delivery or booking. A Gemini failure must not terminate a conversation, corrupt BANT state, fabricate a score/value, or trigger high-intent routing.
