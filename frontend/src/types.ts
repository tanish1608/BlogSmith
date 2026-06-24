export interface Account {
  uid: string;
  email: string | null;
  plan: string;
  keys: Record<string, string | null>;
}

export interface CustomPrompts {
  brand_voice?: string | null;
  discovery?: string | null;
  research?: string | null;
  outline?: string | null;
  draft?: string | null;
  critique?: string | null;
  finalize?: string | null;
  visuals?: string | null;
  distribute?: string | null;
}

export interface ScheduleConfig {
  enabled: boolean;
  cadence: string;
  times: string[];
  timezone: string;
  days_of_week: number[];
  count_per_run: number;
}

export interface DiscoveryConfig {
  source: string;
  seed_topics: string[];
  gsc_site_url?: string | null;
  serp_country: string;
}

export interface Site {
  id: string;
  name: string;
  domain: string;
  brand_voice?: string | null;
  custom_prompts: CustomPrompts;
  image_style?: string | null;
  pillar_cluster_map: Record<string, string[]>;
  internal_links: { title: string; url: string; keywords: string[] }[];
  discovery: DiscoveryConfig;
  schedule: ScheduleConfig;
  author?: { name?: string | null; role?: string | null; url?: string | null };
  content_type?: string | null;
  default_tags?: string[];
  approval_email?: string | null;
}

export interface Run {
  id: string;
  site_id: string;
  status: string;
  topic?: string | null;
  keyword?: string | null;
  error?: string | null;
  stages: Record<string, any>;
}

export interface RunResult {
  id: string;
  site_id: string;
  status: string;
  title?: string | null;
  meta_description?: string | null;
  slug?: string | null;
  markdown?: string | null;
  mdx?: string | null;
  mdx_filename?: string | null;
  tags?: string[];
  content_type?: string | null;
  json_ld?: any;
  images: any[];
  linkedin_thread: string[];
}
