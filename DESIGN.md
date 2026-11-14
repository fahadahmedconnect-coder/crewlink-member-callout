# Member Callout System

## Part 0: Requirements

### What I'm Building

Denise, here's what I'll build for you:

1. **Send announcements** — You write a message, pick your local, hit send. Every active member gets notified.

2. **See who got it** — A live dashboard shows: how many received, how many opened, how many confirmed. You'll know before leaving the hall.

3. **Members can acknowledge** — They open the message and tap "Got it" so you know they saw it.

4. **AI cleanup** — Paste your messy notes, AI turns it into a clear title + body + push preview. You approve before sending.

5. **Nobody sees other locals' stuff** — Local 27's data stays in Local 27. Period.

6. **No double sends** — If you click Send twice, or the system crashes mid-send, nobody gets the message twice.

---

### Assumptions

| Topic | What I Assumed | Why |
|-------|----------------|-----|
| **Who sends** | Leadership accounts only | Members shouldn't broadcast to 22,400 people |
| **Who receives** | Active members only | Retired/suspended members don't get callouts |
| **Leader scope** | Leaders can only send to their own local | Rule 1 — Local 27 leader can't reach Local 42 |
| **Multiple leaders** | Multiple leadership accounts per local allowed, all can send | Unions have several officers |
| **"Immediately"** | Push sent within 60 seconds, inbox syncs when back online | Members in basements/tunnels are offline for hours |
| **Acknowledgment** | Optional per announcement (`needs_ack` flag) | Not every message needs confirmation |
| **RSVP** | Designed but not built | Per the brief |
| **Target audience** | Can filter by classification (e.g., "only apprentices") | Not every message is for everyone |
| **Event time** | Optional `event_at` field for meeting datetime | Useful for RSVP cutoff |
| **Announcement status** | `draft` → `approved` → `sending` → `sent` | AI output starts as draft, human approves |
| **Edit after send** | No | Send a correction announcement instead |
| **Recall/delete** | No | Too complex, members may have already seen it |
| **Urgent flag** | Designed but not built | Could trigger SMS fallback later |
| **Push preview** | 120 characters max, stored separately | PDF requirement |
| **What counts as done** | Denise can send, watch live counts, see acknowledgments. Member can read and acknowledge. Rule 1 and Rule 2 verified. | Minimum viable slice |

#### Account & Registration

| Topic | What I Assumed | Why |
|-------|----------------|-----|
| **Auth model** | Separate `users` table with `local_id` and `role` | Separates login from union membership |
| **Leadership accounts** | Created by platform admin | Prevents unauthorized access |
| **Member registration** | Admin/leadership imports members | Unions have official rosters, no self-signup |
| **Leadership who aren't members** | Allowed (optional `member_id` on users) | Business managers may not be tradespeople |

#### Visibility Rules (Who Sees What)

| Who | Sees Names | Sees Classification | Sees Contact Info | Why |
|-----|------------|---------------------|-------------------|-----|
| **Leadership → Members** | Yes | Yes | No | Need names for "who's coming" list, but system sends notifications — not leadership manually |
| **Members → Members** | No | No | No | Not needed for callouts, protects privacy |
| **Members → Leadership** | No | No | No | Not needed |

**Example — What Denise sees:**
```
Coming (234):
  - John Smith (Journeyman Wireman) ✓
  - Maria Garcia (Apprentice 3rd Year) ✓

No Response Yet (621):
  - Ahmed Hassan (Apprentice 2nd Year)
```

She sees names and classifications. She does NOT see email or phone.

#### AI Feature

| Topic | What I Assumed | Why |
|-------|----------------|-----|
| **AI timeout** | 8 seconds, then fallback to manual entry | Can't block UI forever |
| **AI output** | Goes to `draft` status, never sends directly | Human must approve before sending |
| **AI provider down** | Form stays usable for manual entry | System works without AI |

---

### Concerns

**1. The apprentice contact info is a separate problem.**

You asked: "can members outside our local see the wireman apprentices' contact info?"

This sounds like a leak happening RIGHT NOW — not a feature request. It needs investigation today as a potential Rule 1 breach. In my design, no member sees any other member's info.

**2. Push notifications fail silently (5-10%).**

Members in elevator shafts, underground, rural highways are offline for hours. Push alone won't reach everyone. My design includes an inbox that syncs when they reconnect.

**3. "Before contract talks" is not a real deadline.**

No date was given. I'm building the smallest useful thing first.

**4. Attendance data is sensitive too.**

Who is coming to an emergency meeting during a contractor dispute is union activity data. It gets the same protection as membership — only leadership of that local can see it.

---

### Questions I'd Ask Denise

| Question | Why It Matters | What I Assumed |
|----------|----------------|----------------|
| Can you send to just apprentices, or always the whole local? | Changes targeting logic | Yes, optional filter by classification |
| Who else has leadership access? Can they all send to everyone? | Security + permissions | Multiple leaders per local, all can send |
| What exactly did someone see about apprentice contact info? Where? | Could be a live breach | Treating as real; my design exposes no contact info to members |

---

## Part A: Design

### 1. Data Model

```
users
  id              uuid PK
  email           text UNIQUE
  password_hash   text
  local_id        uuid FK → locals (nullable for superuser)
  role            'member' | 'leadership'
  member_id       uuid FK → members (nullable)
  is_superuser    boolean (Django built-in, for platform admin)

locals
  id              uuid PK
  name            text                    -- "Local 27"

members
  id              uuid PK
  local_id        uuid FK → locals
  full_name       text
  email           text
  classification  text                    -- "Journeyman Wireman"
  status          'active' | 'retired' | 'suspended'

announcements
  id              uuid PK
  local_id        uuid FK → locals
  created_by      uuid FK → users
  title           text
  body            text
  push_preview    varchar(120)            -- max 120 chars for push
  target_class    text (nullable)         -- filter by classification
  needs_ack       boolean DEFAULT false
  source_note     text (nullable)         -- original messy input
  status          'draft' | 'approved' | 'sending' | 'sent'
  approved_by     uuid FK → users (nullable)
  approved_at     timestamptz (nullable)
  sent_at         timestamptz (nullable)
  created_at      timestamptz

announcement_recipients
  id              uuid PK
  announcement_id uuid FK → announcements
  member_id       uuid FK → members
  local_id        uuid                    -- denormalized for fast queries
  status          'pending' | 'sending' | 'sent' | 'failed'
  sent_at         timestamptz (nullable)
  read_at         timestamptz (nullable)
  acked_at        timestamptz (nullable)
  rsvp            'coming' | 'cant' (nullable, design only)

  UNIQUE(announcement_id, member_id)      -- Enforces Rule 2
```

**How we track what each member did:**

| State | How it looks in DB |
|-------|-------------------|
| Nothing (not sent yet) | `status='pending'`, all timestamps null |
| Sent but not read | `status='sent'`, `sent_at` set, `read_at` null |
| Read but not acknowledged | `read_at` set, `acked_at` null |
| Acknowledged | `acked_at` set |
| Coming / Can't (RSVP) | `rsvp='coming'` or `rsvp='cant'` (design only) |

**Key decisions:**
- Separate `users` table for auth (leadership may not be union members)
- Timestamps per action, not single status — answers "did they read before the meeting?"
- `local_id` denormalized on recipients for single-column filtering
- `UNIQUE(announcement_id, member_id)` makes Rule 2 impossible to violate
- `status` field on announcements prevents double-send at API level

---

### 2. The Send Path

**Leadership presses Send at 14:02:**

**Inside the HTTP request (~200ms):**

```
POST /api/leadership/announcements/{id}/send/

1. Authenticate user, check role = 'leadership'
2. Verify announcement.local_id = user.local_id (Rule 1)
3. Verify announcement.status = 'approved'
4. UPDATE announcements SET status = 'sending', sent_at = now()
   WHERE id = {id} AND status = 'approved'
   → If 0 rows affected, already sending/sent — return current state
5. Return 202 Accepted immediately
```

**Leadership waits ~200ms.** UI shows "Sending..." and starts polling.

**Background worker (Django management command, runs separately):**

```
While true:
  1. Find announcements WHERE status = 'sending'

  2. For each announcement, bulk insert recipients:
     INSERT INTO announcement_recipients (announcement_id, member_id, local_id, status)
     SELECT {id}, id, local_id, 'pending'
     FROM members
     WHERE local_id = {local_id} AND status = 'active'
     ON CONFLICT (announcement_id, member_id) DO NOTHING  ← Rule 2

  3. Claim batch of 500 with SKIP LOCKED:
     UPDATE announcement_recipients SET status = 'sending'
     WHERE id IN (
       SELECT id FROM announcement_recipients
       WHERE announcement_id = {id} AND status = 'pending'
       LIMIT 500
       FOR UPDATE SKIP LOCKED
     )
     RETURNING id, member_id

  4. For each recipient in batch:
     - Log "Simulated push to {member.email}" (console)
     - UPDATE status = 'sent', sent_at = now()

  5. When no 'pending' rows left:
     UPDATE announcements SET status = 'sent'

  Sleep 1 second, repeat
```

**Why simple worker instead of Celery:**
- PDF says "minimal config is fine" — Celery adds Redis dependency without benefit
- Protection lives in Postgres (unique constraint, SKIP LOCKED), not in the worker
- Same Rule 2 enforcement whether 1 worker or 10, Celery or simple script
- Easier to demonstrate in `docker compose up`

**Four people watching the status screen:**

- Frontend polls `GET /api/leadership/announcements/{id}/stats/` every 5 seconds
- Endpoint runs one aggregate query:
  ```sql
  SELECT
    COUNT(*) FILTER (WHERE status = 'sent') as sent,
    COUNT(*) FILTER (WHERE read_at IS NOT NULL) as read,
    COUNT(*) FILTER (WHERE acked_at IS NOT NULL) as acked
  FROM announcement_recipients
  WHERE announcement_id = {id}
  ```
- Result cached 2-3 seconds per announcement
- 4 viewers × 1 request/5 seconds = 0.8 QPS (negligible)
- 40 viewers still only hit cache

---

### 3. The Two Rules, By Design

#### Rule 1: Data Isolation

**Where enforced:**

| Layer | Mechanism |
|-------|-----------|
| **Base class** | `LocalScopedViewSet` auto-filters all queries by `user.local_id` |
| **Permissions** | `@require_role('leadership')` decorator on send/create endpoints |
| **Default deny** | No decorator = no access |

```python
class LocalScopedViewSet(ViewSet):
    def get_queryset(self):
        return super().get_queryset().filter(
            local_id=self.request.user.local_id
        )

@require_role('leadership')
class AnnouncementViewSet(LocalScopedViewSet):
    # Automatically scoped to user's local
    pass
```

**What if someone adds endpoint next year and forgets?**
- All views must inherit `LocalScopedViewSet` to work
- CI test walks URL config, fails if any view lacks scoped base class
- Default permission is DENY — undecorated endpoints return 403

**Member vs Leadership boundary:**
- Member endpoints only access "my own recipient row" via `member_id = request.user.member_id`
- Members cannot list other members or see contact info
- Decorator enforces role: `@require_role('member')` or `@require_role('leadership')`

#### Rule 2: No Double Delivery

**Where enforced:**

| Scenario | Protection |
|----------|------------|
| Leadership clicks Send twice | `UPDATE ... WHERE status = 'approved'` returns 0 rows on second click |
| Two API instances handle same request | Postgres row lock picks one winner |
| Worker crashes mid-send | Unclaimed rows stay `pending`, picked up on restart |
| Two workers grab same batch | `FOR UPDATE SKIP LOCKED` — each row claimed by exactly one worker |
| Recipient inserted twice | `UNIQUE(announcement_id, member_id)` constraint — DB rejects duplicate |

**The protection is in Postgres, not in process memory.** This is why it works with 2 instances behind a load balancer.

#### Why Rule 2 Works Behind a Load Balancer

A common mistake: checking "have we sent this?" in application memory.

```python
# BAD - breaks with multiple instances
sent_announcements = set()  # In-memory

def send(announcement_id):
    if announcement_id in sent_announcements:
        return "Already sent"
    sent_announcements.add(announcement_id)
    do_send()
```

```
Instance A                    Instance B
    │                             │
    ├── Check memory: not sent    │
    │                             ├── Check memory: not sent
    ├── Add to set                │
    ├── Send to 2000 members      ├── Add to set
    │                             ├── Send to 2000 members (DUPLICATE!)
```

**Our design uses database-level enforcement:**

```python
# GOOD - works with any number of instances
def send(announcement_id):
    updated = Announcement.objects.filter(
        id=announcement_id,
        status='approved'  # Only approved can be sent
    ).update(status='sending')

    if updated == 0:
        return "Already sending or sent"
    do_send()
```

```
Instance A                    Instance B
    │                             │
    ├── UPDATE WHERE status=approved
    │   (returns 1, wins lock)    │
    │                             ├── UPDATE WHERE status=approved
    │                             │   (returns 0, already 'sending')
    ├── Send to 2000 members      │
    │                             ├── Return current state (no send)
```

**Three layers of database protection:**

| Layer | Mechanism | What It Prevents |
|-------|-----------|------------------|
| API | `UPDATE ... WHERE status='approved'` | Double send requests |
| Insert | `UNIQUE(announcement_id, member_id)` | Duplicate recipient rows |
| Worker | `FOR UPDATE SKIP LOCKED` | Workers claiming same batch |

This is why nginx round-robin across 10 API instances still guarantees exactly-once delivery.

#### Detecting Breaches in Production

| Rule | Detection Method |
|------|------------------|
| **Rule 1** | Log all 403 responses with user context. Alert if user gets 3+ forbidden in a minute. |
| **Rule 1** | Canary account in dummy local pings other locals hourly — should always get 404. |
| **Rule 1** | Weekly audit: `SELECT * FROM announcement_recipients WHERE member.local_id != announcement.local_id` — should return 0. |
| **Rule 2** | Unique constraint makes duplicates impossible. Alert on any constraint violation error. |
| **Rule 2** | Audit query: `SELECT announcement_id, member_id, COUNT(*) HAVING COUNT(*) > 1` — should return 0 rows. |

---

### 4. Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTS                              │
└─────────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌──────────────────┐                ┌──────────────────┐
│ Leadership Screen│                │ Member App       │
│ (Next.js)        │                │ (API only)       │
└────────┬─────────┘                └────────┬─────────┘
         │                                   │
         └─────────────┬─────────────────────┘
                       ▼
              ┌──────────────────┐
              │  Load Balancer   │
              │  (nginx)         │
              │  round-robin     │
              └────────┬─────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Django   │  │ Django   │  │ Django   │
   │ API 1    │  │ API 2    │  │ API n    │
   │          │  │          │  │          │
   │ Stateless│  │ Stateless│  │ Stateless│
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
             ┌────────────────┐
             │   PostgreSQL   │
             │                │
             │ • UNIQUE       │ ← Rule 2: no duplicates
             │ • SKIP LOCKED  │ ← Workers don't collide
             │ • local_id     │ ← Rule 1: scoped queries
             └───────┬────────┘
                     │
         ┌───────────┼───────────┐
         ▼                       ▼
   ┌───────────┐           ┌───────────┐
   │  Worker   │           │  Worker   │
   │ (manage   │           │ (manage   │
   │  command) │           │  command) │
   │           │           │           │
   │ Claim 500 │           │ Claim 500 │
   │ SKIP LOCK │           │ SKIP LOCK │
   └───────────┘           └───────────┘


REQUEST FLOW:
─────────────
POST /send → Validate (Rule 1) → Set status='sending' → Return 202

Workers → Claim batch (SKIP LOCKED) → "Send" push → Mark sent

GET /stats → Cached aggregate → Return {sent, read, acked}
```

---

## What I Cut

**Built in Part B:**
- Create, AI-cleanup, approve, send announcement
- Recipient tracking with sent/read/acked timestamps
- Member read (auto-mark) and acknowledge endpoints
- Leadership stats endpoint with caching
- Rule 1 via LocalScopedViewSet + @require_role decorator
- Rule 2 via UNIQUE constraint + conditional UPDATE

**Not built:**

| Feature | Why Cut | Next Step |
|---------|---------|-----------|
| RSVP ("coming" / "can't") | Design only per brief | Add endpoints; schema ready |
| Member UI | Scope relief allows API-only | Build Flutter inbox later |
| Real push notifications | No FCM credentials needed | Integrate FCM with collapse keys |
| SMS fallback | For urgent messages | Trigger if unread after 15 min |
| Classification filter | Optional feature | Add dropdown to frontend |
| Postgres Row-Level Security | Base class covers this slice | Add policies before multi-team |
| Canary + audit alerts | Monitoring, not behavior | Add with first production deploy |

---

## Future Improvements

| Area | Current | Future |
|------|---------|--------|
| **Worker** | Polling (1 req/sec) | PostgreSQL LISTEN/NOTIFY or Celery + Redis |
| **Stats** | Frontend polls every 5s | WebSockets or Server-Sent Events |
| **Database** | Single Postgres | Read replicas, PgBouncer, Row-Level Security |
| **Push** | Simulated | FCM/APNs with batching, SMS fallback |

Current approach chosen for simplicity — complexity added when evidence shows it's needed.
