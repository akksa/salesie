# Salesie

**An AI salesperson that turns Instagram, Facebook and WhatsApp engagement into sales.**

Small businesses sell through social media, but the sale often stops at the comment section: comments go
unanswered, DMs sit for hours, and nobody tracks who was interested in what. Salesie connects a business's
Meta accounts to a lightweight AI-native CRM. Every comment and DM becomes a contact linked to the post and
product they engaged with, and (from Phase 2) a Muse Spark sales agent follows up, answers from the catalog,
and sends a payment link, moving the deal through the pipeline as it goes.

> Built for the **Meta Global AI Developer Hackathon** (Indie Developer track), Oct 27 – Nov 4, 2026.
> Everything in this repository was written during the hackathon; the git history is the record.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Meta app, accounts, model access | in progress |
| 1 | CRM core, Meta webhook pipeline, simulator, owner UI | **done** (not yet deployed) |
| 2 | Instagram sales loop: private reply → DM → sales agent → payment link → won | **built** (model mocked until API credits) |
| 3 | Post → product mapping with SAM 3.1 + Muse Spark vision | planned |
| 4 | WhatsApp channel (+ voice notes via Muse Voice Transcribe) | planned |
| 5 | Owner dashboard: pipeline board, deal timeline, take over a chat, insights | **built** |

## How it works (Phase 1)

```
Instagram ──webhook──▶ POST /webhooks/meta ──▶ verify X-Hub-Signature-256 (HMAC of raw body)
                                            ──▶ store raw event (deduplicated by body hash) ──▶ 200 to Meta
                                            ──▶ after the response: parse (both comment envelopes, DMs,
                                                echoes, standby) and ingest each event in its own transaction:
                                                contact + identity → post → engagement → deal
                                                conversation → message → deal stage change
Simulator (dashboard) ──▶ builds Meta-shaped payload, signs it ──▶ same receiver functions
Owner dashboard ──▶ /api/* (HTTP Basic) ──▶ catalog, posts, contacts, inbox, deals, webhook events
```

- **Idempotent**: Meta redelivers webhooks; identical bodies are stored once, and comments and messages
  are deduplicated by their Meta ids, so a redelivery in a different batch changes nothing.
- **One bad event can't sink a batch**: each Meta event commits on its own; failures are recorded on the
  stored delivery with the reason, and the dashboard can **replay** it once the cause is fixed.
- **Race-safe**: concurrent deliveries for one shopper produce one contact and one open deal per product
  (savepoints + unique constraints, a per-contact advisory lock, and a partial unique index on deals).
- **Deal rules**: a comment attaches to the shopper's open deal for that product or post (or fills in a
  product-less deal opened by a DM); a DM moves a new deal to *engaged*; a "thanks!" within 14 days of
  a closed deal doesn't open a new one.

## The sales agent (Phase 2)

```
new comment / DM ──▶ ReplyRequest ──▶ runner (per-shopper lock)
   ├─ anything unanswered?  Meta allows a reply?  (DM within 24h of their last message,
   │                                                otherwise one private reply per comment within 7 days)
   ├─ prompt: instructions + shop notes │ facts (deal, product, post) │ conversation history
   ├─ model ⇄ tools, max 6 steps, inside a savepoint (undone if the model fails or runs away)
   │     search_catalog · get_product · note_customer_details · update_deal_stage
   │     create_payment_link · hand_off_to_owner
   ├─ send: Instagram Send API, or recorded only (simulated shoppers / no token)
   └─ agent_runs: trigger, model, every tool call with arguments and result, reply, status
payment link ──▶ /pay/{token} (test checkout) ──▶ deal won ──▶ receipt DM
```

- **Guardrails are in the tools, not the prompt**: arguments are validated (unknown fields rejected),
  everything is scoped to the business, and prices come only from the catalog, so no shopper message can
  produce a cheaper link or another shop's product. Shopper text only ever appears as user messages.
- **Hand-off**: refunds, complaints, requests for a person, or anything the catalog and shop notes can't
  answer pause the agent on that chat and flag it for the owner.
- **Verifiable**: every run is stored with its steps and shown in the inbox ("Why?").
- **Untrusted text stays data**: comments and details the agent saved from shopper messages reach the model
  as quoted JSON in a user message, never in the instructions; only links to Salesie's own checkout can
  leave in a reply (other URLs and bare domains are stripped).
- **Bounded load and spend**: turns for one shopper run one at a time and wait in memory, not on a database
  connection; at most `AGENT_MAX_CONCURRENT_TURNS` run at once; a shopper over
  `AGENT_TURNS_PER_CONTACT_PER_DAY` is handed to the owner. A burst of messages collapses into a few turns,
  and a message that arrives while the model is thinking gets a follow-up turn.
- **Never a silent or phantom reply**: every database write is flushed before a message is sent; temporary
  model errors leave the message for the next turn, other model errors hand the chat to the owner.
- **Checkout integrity**: a new link expires older ones; a link stops working if the deal closes or the
  product's price or availability changes; the test checkout refuses to run with live Instagram sending
  unless explicitly allowed.

### What is mocked right now

| Piece | Now | Switch to real |
|---|---|---|
| Model | `mock-sales-brain`: deterministic rules + the same tools; labeled as a mock everywhere | `LLM_PROVIDER=muse`, `MODEL_API_KEY=…` (Muse Spark 1.3 on Meta Model API). Muse Spark Open on Baseten: `LLM_BASE_URL=https://inference.baseten.co/v1`, `LLM_MODEL=meta-models/muse-spark-open` |
| Instagram sending | recorded in Salesie only | `INSTAGRAM_ACCESS_TOKEN=…` (simulated shoppers still never reach Meta) |
| Payments | built-in test checkout page, no money moves | a real provider implementing `PaymentProvider` |

## The owner dashboard (Phase 5)

- **Pipeline board**: every deal by stage with totals; drag a card to override (paid in cash, lost...).
  Closing a deal retires its unpaid payment links. Cards flag chats the agent handed over ("Needs you").
- **Deal timeline**: every stage change with who made it (system, agent, owner) and why, plus payment links.
- **Take over a chat**: reply from the inbox. The agent pauses on that chat until you resume it. Instagram
  lets a person reply up to 7 days after the shopper's last message (HUMAN_AGENT tag), the agent only 24 hours.
- **Insights**: leads, deals, won revenue, conversion, the funnel, the agent's reply time and hand-offs,
  and *which posts made money*: every sale traced back to the post and channel it came from.

## Run it locally

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24, PostgreSQL server binaries
(any of 16–18; the script uses the newest under `/usr/lib/postgresql`).

```bash
# 1. Private Postgres inside the repo (port 5433), creates backend/.env with DB credentials
scripts/devdb.sh init        # later: scripts/devdb.sh start | stop | status

# 2. Backend
cd backend
# edit .env: set META_APP_SECRET, META_VERIFY_TOKEN, OWNER_PASSWORD (anything for local use)
uv sync
uv run alembic upgrade head
uv run python -m app.seed    # demo shop "Bloom & Thread" (--reset wipes the database first)
uv run python -m app.demo    # optional: 8 shoppers played through the real pipeline (board, inbox, insights)
uv run uvicorn app.main:create_app --factory --port 8000 --no-server-header

# 3. Frontend (another terminal)
cd frontend
npm install
npm run dev                  # http://localhost:5173, log in as OWNER_USERNAME / OWNER_PASSWORD
```

Open **Simulator** in the dashboard to fake an Instagram comment or DM and watch the contact, deal and
conversation appear.

### Tests

```bash
cd backend
uv run pytest --cov=app      # integration tests against a real Postgres (salesie_test DB)
uv run ruff check . && uv run pyright
```

## Connecting a real Instagram account

1. In your Meta app, add the Instagram product and set the webhook callback URL to
   `https://<your-host>/webhooks/meta` with the verify token from `META_VERIFY_TOKEN`.
2. Put the app secret in `META_APP_SECRET`.
3. Subscribe to the `comments` and `messages` fields.
4. Set the business's Instagram account id (the `entry[].id` Meta sends) via `PATCH /api/business`.

While the Meta app is in development mode, Meta only delivers webhooks for people with a role on the app.
That's why the simulator exists: anyone can try the full pipeline without an Instagram account.

## Security notes

- Webhooks: HMAC-SHA256 signature over the raw body (constant-time compare); verify-token handshake.
- Owner API: HTTP Basic, constant-time compare, password must be 16+ characters, and repeated failed
  logins are throttled per client IP (20 per 5 minutes). Behind a reverse proxy, run uvicorn with
  `--proxy-headers --forwarded-allow-ips=<proxy ip>` so the real client IP is used.
- Request bodies are capped at 1 MB while streaming, before routing and auth.
- Security headers (CSP with `frame-ancestors 'none'`, nosniff, HSTS, no-store on `/api`); API docs off
  unless `API_DOCS_ENABLED=true`.
- Text that Postgres can't store (NUL, lone surrogates) is stripped from webhook and API input.
- No CORS is enabled, which (with JSON-only endpoints) is what blocks cross-site requests from a browser
  that has cached the Basic credentials. Keep it that way, or add CSRF protection with it.

## Meta models used

Planned per phase: **Muse Spark** (sales agent with tool calling; image + caption understanding),
**SAM 3.1** (product segmentation from post images), **Muse Voice Transcribe** (WhatsApp voice notes),
optionally **Muse Spark Open** (agent on open weights). Phase 1 is the CRM and webhook foundation they plug into.
