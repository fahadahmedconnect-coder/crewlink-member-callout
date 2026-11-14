# CrewLink - Member Callout System

Union announcement system with Rule 1 (data isolation) and Rule 2 (no double sends).

## Quick Start

```bash
# 1. Configure OpenAI (optional, for AI cleanup)
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY

# 2. Start all services
docker compose up --build

# 3. In another terminal, seed the database
docker compose exec api python manage.py seed_data
```

## Postman Collection

Import `CrewLink.postman_collection.json` into Postman to test all endpoints.

The collection includes:
- All auth endpoints (login for each account)
- AI cleanup
- Leadership endpoints (create, approve, send, stats)
- Member endpoints (list, view, acknowledge)
- Rule 1 & Rule 2 test requests

App runs at:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **Admin**: http://localhost:8000/admin

## TEST ACCOUNTS

```json
{
  "local_27": {
    "leadership": {
      "email": "leader@local27.union",
      "password": "password123"
    },
    "member": {
      "email": "member@local27.union",
      "password": "password123"
    }
  },
  "local_42": {
    "leadership": {
      "email": "leader@local42.union",
      "password": "password123"
    },
    "member": {
      "email": "member@local42.union",
      "password": "password123"
    }
  },
  "admin": {
    "email": "admin@crewlink.com",
    "password": "admin123",
    "url": "http://localhost:8000/admin"
  },
  "seeded_announcement_id": "11111111-1111-1111-1111-111111111111",
  "local_42_member_id": "22222222-2222-2222-2222-222222222222",
  "endpoints": {
    "auth": {
      "login": "POST /api/auth/login/ (body: {email, password}, returns session cookie)",
      "logout": "POST /api/auth/logout/ (cookie auth)",
      "me": "GET /api/auth/me/ (cookie auth)"
    },
    "ai": {
      "cleanup": "POST /api/ai/cleanup/ (cookie auth, body: {messy_text})"
    },
    "leadership": {
      "list": "GET /api/leadership/announcements/ (cookie auth)",
      "create": "POST /api/leadership/announcements/ (cookie auth, body: {title, body, push_preview, needs_ack})",
      "detail": "GET /api/leadership/announcements/{id}/ (cookie auth)",
      "update": "PATCH /api/leadership/announcements/{id}/ (cookie auth)",
      "approve": "POST /api/leadership/announcements/{id}/approve/ (cookie auth)",
      "send": "POST /api/leadership/announcements/{id}/send/ (cookie auth)",
      "stats": "GET /api/leadership/announcements/{id}/stats/ (cookie auth)"
    },
    "member": {
      "list": "GET /api/member/announcements/ (cookie auth)",
      "detail": "GET /api/member/announcements/{id}/ (cookie auth, auto-marks read)",
      "acknowledge": "POST /api/member/announcements/{id}/acknowledge/ (cookie auth)"
    }
  }
}
```

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Login |
| POST | `/api/auth/logout/` | Logout |
| GET | `/api/auth/me/` | Get current user |

### AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/cleanup/` | Clean messy text (standalone, no announcement ID needed) |

### Leadership
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/leadership/announcements/` | List announcements |
| POST | `/api/leadership/announcements/` | Create announcement |
| GET | `/api/leadership/announcements/{id}/` | Get announcement |
| PATCH | `/api/leadership/announcements/{id}/` | Update announcement |
| POST | `/api/leadership/announcements/{id}/approve/` | Approve draft |
| POST | `/api/leadership/announcements/{id}/send/` | Send to members |
| GET | `/api/leadership/announcements/{id}/stats/` | Get delivery stats |

### Member
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/member/announcements/` | List my announcements |
| GET | `/api/member/announcements/{id}/` | View (auto-marks read) |
| POST | `/api/member/announcements/{id}/acknowledge/` | Acknowledge |

## Example Curl Commands

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "leader@local27.union", "password": "password123"}' \
  -c cookies.txt
```

### AI Cleanup (standalone)
```bash
curl -X POST http://localhost:8000/api/ai/cleanup/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"messy_text": "hey guys meeting tmrw 6pm at hall urgent pls come"}'
```

### Create, Approve, Send
```bash
# Create
curl -X POST http://localhost:8000/api/leadership/announcements/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"title": "Test Meeting", "body": "Meeting at 6pm", "push_preview": "Meeting 6pm", "needs_ack": true}'

# Approve
curl -X POST http://localhost:8000/api/leadership/announcements/{id}/approve/ -b cookies.txt

# Send
curl -X POST http://localhost:8000/api/leadership/announcements/{id}/send/ -b cookies.txt

# Stats
curl http://localhost:8000/api/leadership/announcements/{id}/stats/ -b cookies.txt
```

### Member Flow
```bash
# Login as member
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "member@local27.union", "password": "password123"}' \
  -c cookies.txt

# List my announcements
curl http://localhost:8000/api/member/announcements/ -b cookies.txt

# View single announcement (auto-marks as read)
curl http://localhost:8000/api/member/announcements/{id}/ -b cookies.txt

# Acknowledge
curl -X POST http://localhost:8000/api/member/announcements/{id}/acknowledge/ -b cookies.txt
```

## Rule Tests

### Rule 1: Data Isolation
```bash
# Login as Local 42 leader
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "leader@local42.union", "password": "password123"}' \
  -c cookies.txt

# List announcements - should be empty (Local 27 data not visible)
curl http://localhost:8000/api/leadership/announcements/ -b cookies.txt
# Returns: []

# Try to access Local 27 announcement - should fail
curl http://localhost:8000/api/leadership/announcements/{local27-announcement-id}/ -b cookies.txt
# Returns: {"detail":"No Announcement matches the given query."}
```

### Rule 2: No Double Delivery
```bash
# Send same announcement twice rapidly
curl -X POST http://localhost:8000/api/leadership/announcements/{id}/send/ -b cookies.txt &
curl -X POST http://localhost:8000/api/leadership/announcements/{id}/send/ -b cookies.txt &

# Check stats - should show exactly 2000 recipients, NOT 4000
curl http://localhost:8000/api/leadership/announcements/{id}/stats/ -b cookies.txt
```

## Project Structure

```
avialdo/
├── backend/
│   ├── config/           # Django settings
│   ├── core/             # Main app (models, views, urls)
│   │   ├── models.py     # User, Local, Member, Announcement, AnnouncementRecipient
│   │   ├── views.py      # API endpoints
│   │   ├── serializers.py
│   │   ├── permissions.py
│   │   └── management/commands/
│   │       ├── seed_data.py      # Demo data
│   │       └── process_sends.py  # Background worker
│   ├── ai/
│   │   └── cleanup.py    # OpenAI integration
│   ├── .env              # Environment variables (not committed)
│   └── .env.example      # Template
├── frontend/
│   └── app/
│       ├── page.tsx      # Leadership dashboard
│       └── globals.css   # Light theme styles
├── docker-compose.yml
├── DESIGN.md             # Part 0 (Requirements) + Part A (Design)
└── README.md
```

## Tech Stack

- **Backend**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL 15
- **Frontend**: Next.js 14 (React)
- **AI**: OpenAI GPT-4o-mini
- **Container**: Docker Compose

## Key Design Decisions

| Decision | Why |
|----------|-----|
| Simple worker (not Celery) | PDF says "minimal config is fine" - no Redis needed |
| UNIQUE constraint for Rule 2 | Database enforces no duplicates, not application code |
| `FOR UPDATE SKIP LOCKED` | Multiple workers can run without collisions |
| `LocalScopedViewSet` base class | Rule 1 enforced in one place |
| Session auth (not JWT) | Simpler for browser-based frontend |
| Standalone AI cleanup endpoint | Works for new announcements (no ID needed) |
"# crewlink-member-callout" 
