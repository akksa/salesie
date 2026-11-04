# Salesie

**An AI salesperson that turns Instagram, Facebook and WhatsApp engagement into sales.**

Small businesses sell through social media, but the sale often stops at the comment section: comments go
unanswered, DMs sit for hours, and nobody tracks who was interested in what. Salesie connects a business's
Meta accounts to a lightweight AI-native CRM. Every comment and DM becomes a contact linked to the post and
product they engaged with, and a **Muse Spark** sales agent follows up in private messages, answers from the
catalog, and sends a payment link, moving the deal through the pipeline as it goes.

> Built for the **Meta Global AI Developer Hackathon** (Indie Developer track), Oct 27 – Nov 4, 2026.
> Everything in this repository was written during the hackathon; the git history is the record.

## It works on a real Facebook Page

Salesie runs the **Bloom & Thread** Facebook Page, a demo handmade-fashion shop whose logo, cover, product
photos and offer posts were made with **Muse Image**. A real comment on the Linen Wrap Dress post, answered by
**Muse Spark 1.3**:

| | Messenger |
|---|---|
| **Salesie** (private reply to the comment "price") | Hi Saravanakumar, the Linen Wrap Dress is Rs 2499 in sage, sand and navy, sizes XS to XL. Which colour and size would you like? |
| **Shopper** | Sand color and Size M |
| **Salesie** | Perfect, sand in M is lovely. Shall I set up checkout for 1 piece, and which city should we ship to? |
| **Shopper** | Yes, Theni, 625533 |
| **Salesie** | Great, here is your secure checkout link for the sand M: https://…/pay/… |
| **Salesie** (after the test payment) | Payment received, thank you! 🎉 Your Linen Wrap Dress is confirmed. We'll be in touch about delivery. (Test checkout: no money was taken.) |

In the dashboard that one comment became a contact, a deal linked to the post and product (size, colour,
shipping city saved by the agent), and a **won** sale of ₹2,499 traced back to the post that made it.

## Meta models used

| Model | Where | What it does |
|---|---|---|
| **Muse Spark 1.3** (Meta Model API) | `backend/app/agent/` | The sales agent: tool calling over the catalog and CRM (search, product details, saving the shopper's choices, deal stages, payment links, hand-off to the owner), with `reasoning_effort: low` for 5–15 s replies |
| **Muse Image 1.0** (Meta Model API) | `docs/brand/` | The shop's brand: cover, logo, six product photos and three offer posts. The bundle images were made with the edits endpoint from the product photos, so the tote and earrings look the same everywhere |

## Status

| Phase | What | State |
|---|---|---|
| 0 | Meta app, Page, model access | **done**: app published (standard access), Muse Spark + Muse Image on Meta Model API |
| 1 | CRM core, Meta webhook pipeline, simulator, owner UI | **done** |
| 2 | Sales loop: comment → private reply → DM → agent → payment link → won | **live** on Facebook Page + Messenger; Instagram built and tested with the simulator, not yet connected to a real account |
| 3 | Post → product mapping with SAM 3.1 + Muse Spark vision | not built (posts are linked to products by the product name in the caption) |
| 4 | WhatsApp channel (+ voice notes via Muse Voice Transcribe) | not built |
| 5 | Owner dashboard: pipeline board, deal timeline, take over a chat, insights | **done** |

## How it works (Phase 1)

```
Facebook / Instagram ──webhook──▶ POST /webhooks/meta ──▶ verify X-Hub-Signature-256 (HMAC of raw body)
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
   ├─ send: Messenger / Instagram Send API, or recorded only (simulated shoppers / no token)
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
  as quoted JSON in a user message, never in the instructions (Facebook names included); only links to
  Salesie's own checkout can leave in a reply (other URLs and bare domains, including look-alike scripts and
  fullwidth dots, are stripped), and markdown is turned into plain text because Messenger shows it as typed.
- **One person, one contact**: someone who messaged the Page and later comments arrives under a different
  Facebook id; Meta's answer to the private reply reveals their Messenger id, and Salesie merges the two
  contacts (conversations, deals and history) into one.
- **Never a half-finished reply**: a reply Meta reports as cut off by the token limit is never sent; the
  shopper gets a holding message and the owner gets the chat.
- **Bounded load and spend**: turns for one shopper run one at a time and wait in memory, not on a database
  connection; at most `AGENT_MAX_CONCURRENT_TURNS` run at once; a shopper over
  `AGENT_TURNS_PER_CONTACT_PER_DAY` is handed to the owner. A burst of messages collapses into a few turns,
  and a message that arrives while the model is thinking gets a follow-up turn.
- **Never a silent or phantom reply**: every database write is flushed before a message is sent; temporary
  model errors leave the message for the next turn, other model errors hand the chat to the owner.
- **Checkout integrity**: a new link expires older ones; a link stops working if the deal closes or the
  product's price or availability changes; the test checkout refuses to run with live Instagram sending
  unless explicitly allowed.

### What's real and what's not

| Piece | Now | Settings |
|---|---|---|
| Model | **Muse Spark 1.3** on Meta Model API. Without a key, `mock-sales-brain` (deterministic rules + the same tools, labeled as a mock everywhere) runs instead | `LLM_PROVIDER=muse`, `MODEL_API_KEY=…`, `LLM_REASONING_EFFORT=low`. Muse Spark Open on Baseten: `LLM_BASE_URL=https://inference.baseten.co/v1`, `LLM_MODEL=meta-models/muse-spark-open` |
| Facebook Page + Messenger | **live** | `FACEBOOK_PAGE_ACCESS_TOKEN=…`, then `uv run python -m app.meta.facebook_setup` |
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

## Connecting a Facebook Page

1. In your Meta app, give a Page access token these permissions: `pages_show_list`, `pages_messaging`,
   `pages_read_engagement`, `pages_manage_metadata` (add `pages_manage_posts` only to publish posts).
2. Set the app's webhook callback URL to `https://<your-host>/webhooks/meta` with the verify token from
   `META_VERIFY_TOKEN`, and put the app secret in `META_APP_SECRET`.
3. Put the token in `FACEBOOK_PAGE_ACCESS_TOKEN` and run `uv run python -m app.meta.facebook_setup`. It
   subscribes the Page to `feed`, `messages` and `message_echoes`, saves the Page id, and imports the Page's
   posts, linking each to the product its caption names.
4. **Publish the app.** In development mode Meta delivered Messenger webhooks but no Page `feed` events
   (comments) at all; they started the moment the app was published. Standard access is enough: the app can
   still only message people with a role on it until Meta reviews `pages_messaging`.
5. Turn off the Page's Messenger automations (Business Suite → Inbox → Automations): Salesie treats any
   message sent from the Page as the owner replying and stays quiet.

Privacy policy for the app: [docs/privacy.md](docs/privacy.md). Brand kit, prompts and post captions:
[docs/brand-kit.md](docs/brand-kit.md).

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

## Next

- **SAM 3.1 + Muse Spark vision** to recognise the product in a new post's photo, instead of relying on the
  caption naming it.
- **WhatsApp**, with **Muse Voice Transcribe** for voice notes.
- **Muse Spark Open** on partner inference, as an open-weights option for the agent.
- Meta's review of `pages_messaging`, so the agent can message every shopper, not only people with a role
  on the app; and a real payment provider.
