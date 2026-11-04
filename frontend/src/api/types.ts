/**
 * TypeScript mirror of backend/app/schemas.py (and the enums in backend/app/models.py).
 * Datetimes arrive as ISO-8601 strings. Money is integer minor units + the business currency.
 */

export const CHANNELS = ["instagram", "whatsapp", "facebook", "messenger"] as const;
export type Channel = (typeof CHANNELS)[number];

export const DEAL_STAGES = ["new", "engaged", "qualified", "payment_sent", "won", "lost"] as const;
export type DealStage = (typeof DEAL_STAGES)[number];

export const PRODUCT_STATUSES = ["active", "draft"] as const;
export type ProductStatus = (typeof PRODUCT_STATUSES)[number];

export type EngagementKind = "comment" | "reaction";
export type Direction = "inbound" | "outbound";
export type Author = "contact" | "agent" | "owner";
export type WebhookStatus = "received" | "processed" | "failed";
export type AgentTrigger = "comment" | "dm";
export type AgentRunStatus = "replied" | "skipped" | "handed_off" | "blocked" | "failed";

/** ISO-8601 datetime string as serialised by Pydantic. */
export type IsoDateTime = string;

/** JSON value allowed in product attributes (`dict[str, Any]`). */
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type Attributes = Record<string, JsonValue>;

// --- app config / business ---------------------------------------------------

export interface AppConfig {
  simulator_enabled: boolean;
}

export interface BusinessOut {
  id: number;
  name: string;
  currency: string;
  ig_account_id: string | null;
  fb_page_id: string | null;
  wa_phone_number_id: string | null;
  sales_notes: string | null;
}

export interface BusinessUpdate {
  name?: string;
  currency?: string;
  ig_account_id?: string | null;
  fb_page_id?: string | null;
  wa_phone_number_id?: string | null;
  /** Shipping, returns, payment options: what the agent may quote. Max 4000 chars. */
  sales_notes?: string | null;
}

// --- catalog -----------------------------------------------------------------

export interface ProductIn {
  name: string;
  description?: string | null;
  attributes?: Attributes;
  price_minor?: number | null;
  image_url?: string | null;
  status?: ProductStatus;
}

export type ProductUpdate = Partial<ProductIn>;

export interface ProductOut {
  id: number;
  name: string;
  description: string | null;
  attributes: Attributes;
  price_minor: number | null;
  image_url: string | null;
  status: ProductStatus;
  created_at: IsoDateTime;
}

export interface PostIn {
  channel?: Channel;
  external_id: string;
  caption?: string | null;
  image_url?: string | null;
  permalink?: string | null;
  product_id?: number | null;
}

export interface PostUpdate {
  caption?: string | null;
  image_url?: string | null;
  permalink?: string | null;
  product_id?: number | null;
}

export interface PostOut {
  id: number;
  channel: Channel;
  external_id: string;
  caption: string | null;
  image_url: string | null;
  permalink: string | null;
  product_id: number | null;
  product_name: string | null;
  engagement_count: number;
  created_at: IsoDateTime;
}

// --- CRM ---------------------------------------------------------------------

export interface IdentityOut {
  channel: Channel;
  external_id: string;
  username: string | null;
}

export interface DealOut {
  id: number;
  contact_id: number;
  contact_name: string;
  stage: DealStage;
  channel: Channel;
  product_id: number | null;
  product_name: string | null;
  source_post_id: number | null;
  amount_minor: number | null;
  /** What the agent learned, e.g. `{ size: "S" }`. Schema says dict[str, Any]; values are usually strings. */
  details: Record<string, JsonValue>;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface EngagementOut {
  id: number;
  kind: EngagementKind;
  channel: Channel;
  text: string | null;
  post_id: number | null;
  occurred_at: IsoDateTime;
}

export interface ContactListItem {
  id: number;
  display_name: string;
  identities: IdentityOut[];
  latest_deal: DealOut | null;
  last_activity_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface MessageOut {
  id: number;
  direction: Direction;
  author: Author;
  text: string | null;
  sent_at: IsoDateTime;
  /** Set on agent replies; links to the AgentRunOut that produced it. */
  agent_run_id: number | null;
}

export interface ConversationListItem {
  id: number;
  contact_id: number;
  contact_name: string;
  channel: Channel;
  agent_paused: boolean;
  /** "agent": it handed the chat to you; "owner": you paused it or took over. */
  paused_by: Actor | null;
  /** Human-readable why (hand-off reason, or which owner action). Display only. */
  paused_reason: string | null;
  last_inbound_at: IsoDateTime | null;
  last_message: MessageOut | null;
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageOut[];
}

export interface ConversationUpdate {
  agent_paused?: boolean;
}

export interface ContactDetail extends ContactListItem {
  engagements: EngagementOut[];
  deals: DealOut[];
  conversations: ConversationListItem[];
}

// --- webhooks & simulator ----------------------------------------------------

export interface WebhookEventOut {
  id: number;
  object_type: string;
  simulated: boolean;
  status: WebhookStatus;
  error: string | null;
  received_at: IsoDateTime;
  processed_at: IsoDateTime | null;
}

// --- agent -------------------------------------------------------------------

export interface AgentStatusOut {
  enabled: boolean;
  model: string;
  is_mock: boolean;
  /** "live" = sent via Instagram's Send API; "recorded" = kept in Salesie only. */
  instagram_sending: "live" | "recorded" | (string & {});
  payments: string;
}

/**
 * One run of the sales agent. `steps` is untyped JSON on the server
 * (`list[dict[str, Any]]`); parse it with `parseSteps` in features/agent/steps.ts.
 */
export interface AgentRunOut {
  id: number;
  contact_id: number;
  conversation_id: number | null;
  trigger: AgentTrigger;
  status: AgentRunStatus;
  model: string;
  steps: Record<string, unknown>[];
  reply_text: string | null;
  error: string | null;
  started_at: IsoDateTime;
  finished_at: IsoDateTime;
}

/** Simulator response: the stored event plus what it created (conversation_id is null for a comment alone). */
export interface SimulationResult extends WebhookEventOut {
  contact_id: number | null;
  conversation_id: number | null;
  /** The simulator waits for the agent, so its runs (and reply) already exist. */
  agent_runs: AgentRunOut[];
}

export interface SimulatedCommentIn {
  post_id: number;
  username: string;
  text: string;
}

export interface SimulatedDirectMessageIn {
  username: string;
  text: string;
}

// --- errors ------------------------------------------------------------------

/** One entry of a FastAPI 422 `detail` array. */
export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type?: string;
}

// --- phase 5: pipeline, deal detail, owner messages, insights ---------------------

export type Actor = "system" | "agent" | "owner";
export type PaymentStatus = "open" | "paid" | "expired";

export interface OwnerMessageIn {
  text: string;
}

/** Either or both. `amount_minor` records e.g. a cash sale. */
export interface DealUpdate {
  stage?: DealStage;
  amount_minor?: number;
}

export interface StageChangeOut {
  from_stage: DealStage | null;
  to_stage: DealStage;
  actor: Actor;
  reason: string | null;
  created_at: IsoDateTime;
}

export interface PaymentLinkOut {
  id: number;
  status: PaymentStatus;
  quantity: number;
  amount_minor: number;
  currency: string;
  url: string;
  created_at: IsoDateTime;
  paid_at: IsoDateTime | null;
}

export interface PostBrief {
  id: number;
  external_id: string;
  caption: string | null;
  image_url: string | null;
  permalink: string | null;
}

export interface PipelineCard extends DealOut {
  conversation_id: number | null;
  agent_paused: boolean;
  /** The agent handed this chat over (refund, complaint, a question it couldn't answer). */
  needs_owner: boolean;
  source_post: PostBrief | null;
  last_message: string | null;
  last_message_author: Author | null;
  last_activity_at: IsoDateTime | null;
}

export interface PipelineColumn {
  stage: DealStage;
  count: number;
  amount_minor: number;
  deals: PipelineCard[];
}

export interface PipelineOut {
  currency: string;
  /** Chats the agent handed over that are waiting for the owner. */
  needs_owner: number;
  /** count/amount_minor cover every deal; `deals` holds at most 100 per column, newest first. */
  columns: PipelineColumn[];
}

export interface DealDetail extends PipelineCard {
  /** Oldest first. */
  stage_changes: StageChangeOut[];
  payment_links: PaymentLinkOut[];
}

export interface FunnelStep {
  stage: DealStage;
  /** Deals that got at least this far. */
  reached: number;
}

export interface PostPerformance {
  post: PostBrief;
  product_name: string | null;
  leads: number;
  deals: number;
  won: number;
  revenue_minor: number;
}

export interface ChannelPerformance {
  channel: Channel;
  deals: number;
  won: number;
  revenue_minor: number;
}

export interface InsightsOut {
  currency: string;
  days: number;
  leads: number;
  deals: number;
  won: number;
  revenue_minor: number;
  /** won / deals opened in the period, 0-1. */
  conversion_rate: number | null;
  agent_replies: number;
  median_agent_reply_seconds: number | null;
  handoffs: number;
  funnel: FunnelStep[];
  by_post: PostPerformance[];
  by_channel: ChannelPerformance[];
}
