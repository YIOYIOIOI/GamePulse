// Shapes returned by the GamePulse API (src/quality/api.py).

export interface Rate {
  n: number;
  negative: number;
  rate: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export type ComparisonStatus =
  | "descriptive_comparison"
  | "insufficient_sample"
  | "incomplete_coverage"
  | "incomplete_window";

export interface Comparison {
  before: Rate;
  after: Rate;
  delta: number | null;
  ci_low: number | null;
  ci_high: number | null;
  status: ComparisonStatus;
  p_value: number | null;
  min_per_period: number;
  language_adjusted: {
    status: string;
    delta: number | null;
    ci_low: number | null;
    ci_high: number | null;
    included_before: number;
    included_after: number;
  };
}

export interface Monitor extends Comparison {
  alert: boolean;
  window: { before_start: string; boundary: string; end: string };
}

export interface ReleaseStudy extends Comparison {
  release_id: string;
  title: string;
  tag: string;
  source_url: string;
  published_at: string;
  window_before_start: string;
  window_after_end: string;
  other_releases: { tag: string; published_at: string }[];
}

export interface Coverage {
  source: string;
  pages: number;
  raw_rows: number;
  complete: boolean;
  stop_reason: string;
  accepted: number;
  quarantined: number;
  scope: string;
  excluded_prs?: number;
  reported_matching?: number;
}

export interface Cue {
  text: string;
  start: number;
  end: number;
}

export interface Evidence {
  id: string;
  product: string;
  source: "steam" | "github_issues";
  title: string;
  text: string;
  source_url: string;
  language: string;
  created_at: string;
  updated_at: string;
  recommended: number | null;
  state?: string | null;
  labels?: string[];
  categories?: string[];
  playtime_at_review_minutes?: number | null;
  helpful_votes: number | null;
  cues?: Cue[];
}

export interface CategoryPeriod {
  mentions: number;
  negative: number;
  reviews: number;
}

export interface Category {
  key: string;
  label: string;
  review_mentions: number;
  negative_reviews: number;
  review_denominator: number;
  github_mentions: number;
  open_issues: number;
  trend: { previous: CategoryPeriod; recent: CategoryPeriod };
  examples: Evidence[];
}

export interface ProductReport {
  key: string;
  name: string;
  app_id: number;
  repo: string;
  identity: {
    store_url: string;
    official_identity_url: string;
    developers: string[];
  };
  recommendation: Rate;
  languages: (Rate & { language: string })[];
  daily: (Rate & { day: string; observed: boolean })[];
  weekly: (Rate & { week: string })[];
  monitor: Monitor;
  categories: Category[];
  cohorts: (Rate & { cohort: string })[];
  issues: { open?: number; closed?: number };
  release_studies: ReleaseStudy[];
  releases_outside_window?: number;
  coverage: Record<string, Coverage>;
  quality: {
    trend_allowed: boolean;
    quarantined: number;
    rules_language_covered: number;
    rule_denominator: number;
    warnings: string[];
  };
}

export interface Report {
  run_id: string;
  as_of: string;
  window_start: string;
  fingerprint: string;
  raw_page_count: number;
  metric_version: string;
  taxonomy_version: string;
  products: ProductReport[];
  method: {
    recommendation: string;
    interval: string;
    releases: string;
    cohorts: string;
    mentions: string;
    boundaries: string[];
  };
}

export interface Run {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: "queued" | "running" | "completed" | "failed";
  fingerprint: string | null;
  error: string | null;
  progress: {
    product?: string;
    source?: string;
    records?: number;
    message?: string;
  };
  config: { products: string[]; days: number; replayed_from?: string };
}

export type FollowUpStatus =
  "pending" | "investigating" | "confirmed" | "closed";

export interface FollowUp {
  id: string;
  run_id: string;
  product: string;
  title: string;
  evidence_ids: string[];
  status: FollowUpStatus;
  owner: string;
  revision: number;
  created_at: string;
  updated_at: string;
  history: {
    at: string;
    action: "created" | "updated";
    note: string;
    actor: string;
    status: FollowUpStatus;
    previous_status: FollowUpStatus | null;
    owner: string;
  }[];
}

export interface EvidencePage {
  run_id: string;
  total: number;
  limit: number;
  offset: number;
  rows: Evidence[];
}

export interface EvidenceDetail {
  evidence: Evidence;
  lineage: {
    page_id: string;
    sha256: string;
    request_url: string;
    fetched_at: string;
    source_fetched_at?: string;
    json_pointer: string;
    record: unknown;
  };
  mentions: { category: string; cues: Cue[] }[];
}

export type Role = "owner" | "reviewer" | "analyst" | "viewer";

export interface Session {
  team_mode: boolean;
  principal: { id: string; name: string; role: Role; workspace: string };
}

export interface Member {
  id: string;
  name: string;
  workspace: string;
  role: Role;
  created_at: string;
  revoked: number;
}

export interface Backup {
  id: string;
  at?: string;
  path: string;
  bytes: number;
  files: number;
  sha256: string;
}

export interface Game {
  key: string;
  name: string;
  app_id: number;
  /** owner/name of the public GitHub repository, or "" when none is linked. */
  repo: string;
  added_at: string;
  /** The newest snapshot that collected this game, or null before its first sync. */
  latest: { run_id: string; as_of: string; reviews: number } | null;
}

export interface GameSearchResult {
  app_id: number;
  name: string;
  image: string;
  added: boolean;
}
