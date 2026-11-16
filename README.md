# DocDesk

A ticket-tracking API built with FastAPI. Tickets live in an in-memory dict for now
(`app/store.py`), so they disappear when the server restarts. The routes and schemas
are meant to stay as the storage behind them changes.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
uv sync                        # create .venv and install dependencies
cp .env.example .env           # then edit values if you like
uv run fastapi dev             # serves app.main:app on http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000/docs> for the interactive Swagger UI.

Run the tests with `uv run pytest`.

### Configuration

Settings are typed (`app/config.py`, pydantic-settings) and read from environment
variables first, then from `.env`, then fall back to defaults. `.env` is git-ignored;
`.env.example` is the committed template.

| Variable        | Default    | Meaning                                    |
| --------------- | ---------- | ------------------------------------------ |
| `APP_NAME`      | `DocDesk`  | Title shown in `/docs`                     |
| `API_KEY`       | `dev-key`  | Reserved for later weeks; not used yet     |
| `MAX_PAGE_SIZE` | `100`      | Largest `limit` accepted by `GET /tickets` |

A real environment variable beats `.env`: `MAX_PAGE_SIZE=10 uv run fastapi dev`.

## Layout

```
app/
  main.py             FastAPI(), include_router, GET /health
  config.py           Settings (pydantic-settings)
  schemas.py          Status, TicketCreate, TicketUpdate, TicketOut
  store.py            TicketStore: add, get, all, update (dict inside)
  routers/tickets.py  POST, GET list, GET one, PATCH
tests/                pytest suite for every route
```

## Ticket

| Field             | Type                              | Notes                                      |
| ----------------- | --------------------------------- | ------------------------------------------ |
| `id`              | int                               | Assigned by the server                     |
| `title`           | string, 5 to 200 characters       |                                            |
| `body`            | string, at least 10 characters    |                                            |
| `status`          | `open` \| `answered` \| `closed`  | Starts as `open`                           |
| `fastapi_version` | string or null                    | Optional                                   |
| `created_at`      | datetime (UTC)                    | Assigned by the server                     |

Leading and trailing whitespace is stripped from `title` and `body` before the length
checks, so a whitespace-only title is rejected.

## Routes

| Method  | Path             | Success | Failures                         |
| ------- | ---------------- | ------- | -------------------------------- |
| `GET`   | `/health`        | 200     | none                             |
| `POST`  | `/tickets`       | 201     | 422 invalid input                |
| `GET`   | `/tickets`       | 200     | 422 bad `status`, `limit` or `offset` |
| `GET`   | `/tickets/{id}`  | 200     | 404 missing, 422 non-integer id  |
| `PATCH` | `/tickets/{id}`  | 200     | 404 missing, 422 invalid input   |

All examples below are real output from a running server (the timestamps differ on
every run).

### `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

### `POST /tickets`

The client sends `title`, `body` and optionally `fastapi_version`. It cannot set `id`,
`status` or `created_at`: the server assigns them, and any of those keys in the request
body are ignored. This is deliberate: `TicketCreate` simply does not declare them.

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Cannot start the server", "body": "uvicorn exits immediately on startup", "fastapi_version": "0.115.0"}'
```

`201 Created`

```json
{
  "id": 1,
  "title": "Cannot start the server",
  "body": "uvicorn exits immediately on startup",
  "status": "open",
  "fastapi_version": "0.115.0",
  "created_at": "2026-11-16T14:40:51.255700Z"
}
```

Sending the server-owned fields anyway changes nothing. Here the client also sends
`id`, `status` and `created_at`:

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Cannot start the server", "body": "uvicorn exits immediately on startup", "fastapi_version": "0.115.0", "id": 999, "status": "closed", "created_at": "2000-01-01T00:00:00Z"}'
```

`201 Created`: `id` is `1` (not 999), `status` is `open` (not `closed`) and
`created_at` is the server's clock (not the year 2000).

```json
{
  "id": 1,
  "title": "Cannot start the server",
  "body": "uvicorn exits immediately on startup",
  "status": "open",
  "fastapi_version": "0.115.0",
  "created_at": "2026-11-16T14:54:17.348657Z"
}
```

Failure: a title shorter than 5 characters gives `422`.

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title": "Hi", "body": "too short"}'
```

`422 Unprocessable Content` (one entry per invalid field; the `body` error is
trimmed here)

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "title"],
      "msg": "String should have at least 5 characters",
      "input": "Hi",
      "ctx": {"min_length": 5}
    }
  ]
}
```

### `GET /tickets`

Query parameters, all optional:

| Parameter | Default | Meaning                                                        |
| --------- | ------- | -------------------------------------------------------------- |
| `status`  | (all)   | Only tickets with this status: `open`, `answered`, `closed`    |
| `limit`   | `20`    | Page size, 1 to `MAX_PAGE_SIZE` (default is `MAX_PAGE_SIZE` if that is below 20) |
| `offset`  | `0`     | Number of tickets to skip                                      |

```bash
curl "http://127.0.0.1:8000/tickets?status=open&limit=1"
```

`200 OK`

```json
[
  {
    "id": 1,
    "title": "Cannot start the server",
    "body": "uvicorn exits immediately on startup",
    "status": "open",
    "fastapi_version": "0.115.0",
    "created_at": "2026-11-16T14:40:51.255700Z"
  }
]
```

Failure: an unknown status gives `422`.

```bash
curl "http://127.0.0.1:8000/tickets?status=bogus"
```

`422 Unprocessable Content`

```json
{
  "detail": [
    {
      "type": "enum",
      "loc": ["query", "status"],
      "msg": "Input should be 'open', 'answered' or 'closed'",
      "input": "bogus",
      "ctx": {"expected": "'open', 'answered' or 'closed'"}
    }
  ]
}
```

### `GET /tickets/{id}`

```bash
curl http://127.0.0.1:8000/tickets/1
```

`200 OK`

```json
{
  "id": 1,
  "title": "Cannot start the server",
  "body": "uvicorn exits immediately on startup",
  "status": "open",
  "fastapi_version": "0.115.0",
  "created_at": "2026-11-16T14:40:51.255700Z"
}
```

Failure: a ticket that does not exist gives `404`.

```bash
curl http://127.0.0.1:8000/tickets/99
```

`404 Not Found`

```json
{"detail": "Ticket 99 not found"}
```

### `PATCH /tickets/{id}`

Send only the fields to change (`title` and/or `status`). Fields you leave out stay
as they were. An explicit `null` is rejected rather than treated as "clear this
field".

```bash
curl -X PATCH http://127.0.0.1:8000/tickets/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "answered"}'
```

`200 OK` (only `status` changed)

```json
{
  "id": 1,
  "title": "Cannot start the server",
  "body": "uvicorn exits immediately on startup",
  "status": "answered",
  "fastapi_version": "0.115.0",
  "created_at": "2026-11-16T14:40:51.255700Z"
}
```

Failure: a ticket that does not exist gives `404`.

```bash
curl -X PATCH http://127.0.0.1:8000/tickets/99 \
  -H "Content-Type: application/json" \
  -d '{"status": "closed"}'
```

`404 Not Found`

```json
{"detail": "Ticket 99 not found"}
```

Invalid input, such as `{"title": null}`, an unknown status or a too-short title, gives
`422` and leaves the stored ticket unchanged.

## The six steps a request goes through

Following `POST /tickets` from the network to the response:

1. **Receive.** The ASGI server (uvicorn) accepts the connection, parses the raw HTTP
   request into method, path, headers and body, and hands it to the FastAPI `app`.
2. **Route.** FastAPI matches the method and path against the registered routes
   (`app/main.py` includes the router from `app/routers/tickets.py`). No match gives
   404 (wrong path) or 405 (wrong method).
3. **Validate input.** FastAPI reads the path, query and JSON body and validates them
   with Pydantic against the function signature (`TicketCreate`, `ticket_id: int`,
   the `status` enum, `limit` bounds). Any failure stops here with a `422` and the
   handler never runs.
4. **Run the handler.** The path operation function runs with the already-validated
   values and calls the store (`store.add(...)`). Raising `HTTPException` (for example
   404 when the ticket is missing) ends the request here with that status.
5. **Filter the output.** The returned value is validated and trimmed to the
   `response_model` (`TicketOut`), so only declared fields reach the client.
6. **Serialize and send.** FastAPI converts the result to JSON (datetimes become
   ISO 8601 strings), applies the route's status code (`201` for create) and the
   response goes back through uvicorn to the client.
