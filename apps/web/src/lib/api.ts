const BASE = import.meta.env.VITE_API_URL || "";

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function authedRequest<T>(path: string, adminKey: string, init?: RequestInit): Promise<T> {
  return request<T>(path, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminKey}` },
  });
}

export const api = {
  dashboard: () => request<DashboardData>("/api/dashboard"),

  players: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<Player>>(`/api/players${qs}`);
  },
  player: (tag: string) => request<Player>(`/api/players/${encodeURIComponent(tag)}`),

  wars: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<War>>(`/api/wars${qs}`);
  },
  war: (id: number) => request<WarDetail>(`/api/wars/${id}`),

  raids: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<PaginatedResponse<Raid>>(`/api/raids${qs}`);
  },
  raid: (id: number) => request<RaidDetail>(`/api/raids/${id}`),

  trackedClans: () => request<{ data: TrackedClan[] }>("/api/tracked-clans"),
  addTrackedClan: (clan_tag: string, note: string | undefined, key: string) =>
    authedRequest<TrackedClan>("/api/tracked-clans", key, {
      method: "POST",
      body: JSON.stringify({ clan_tag, note }),
    }),
  removeTrackedClan: (tag: string, key: string) =>
    authedRequest<void>(`/api/tracked-clans/${encodeURIComponent(tag)}`, key, { method: "DELETE" }),

  trackedPlayers: () => request<{ data: TrackedPlayer[] }>("/api/tracked-players"),
  addTrackedPlayer: (player_tag: string, note: string | undefined, key: string) =>
    authedRequest<TrackedPlayer>("/api/tracked-players", key, {
      method: "POST",
      body: JSON.stringify({ player_tag, note }),
    }),
  removeTrackedPlayer: (tag: string, key: string) =>
    authedRequest<void>(`/api/tracked-players/${encodeURIComponent(tag)}`, key, { method: "DELETE" }),

  legends: () => request<LegendsLeaderboard>("/api/legends"),
  legendsPlayerDays: (tag: string) =>
    request<{ legends_days: string[] }>(`/api/legends/${encodeURIComponent(tag)}/days`),
  legendsPlayer: (tag: string, legendsDay?: string) => {
    const qs =
      legendsDay != null && legendsDay !== ""
        ? `?legends_day=${encodeURIComponent(legendsDay)}`
        : "";
    return request<LegendsPlayerDetail>(`/api/legends/${encodeURIComponent(tag)}${qs}`);
  },

  verifyAdmin: (key: string) =>
    authedRequest<{ ok: boolean }>("/api/admin/verify", key, { method: "POST" }),
  deletePlayer: (tag: string, key: string) =>
    authedRequest<void>(`/api/players/${encodeURIComponent(tag)}`, key, { method: "DELETE" }),
  deleteWar: (id: number, key: string) =>
    authedRequest<void>(`/api/wars/${id}`, key, { method: "DELETE" }),
  deleteRaid: (id: number, key: string) =>
    authedRequest<void>(`/api/raids/${id}`, key, { method: "DELETE" }),
};

export interface DashboardData {
  total_clans: number;
  total_players: number;
  total_wars: number;
  active_wars: number;
  total_raids: number;
  recent_wars: War[];
  recent_raids: Raid[];
}

export interface Player {
  tag: string;
  name: string;
  clan_tag: string | null;
  town_hall_level: number;
  exp_level: number;
  trophies: number;
  best_trophies: number;
  war_stars: number;
  attack_wins: number;
  defense_wins: number;
  role: string | null;
  war_preference: string | null;
  clan_capital_contributions: number;
  league_name: string | null;
  updated_at: string;
  /** Set when no longer on any tracked clan roster (and not always-tracked). Detection time, not historical leave. */
  left_tracked_roster_at?: string | null;
  roster_sort_bucket?: number;
  is_always_tracked?: boolean;
}

export interface War {
  id: number;
  clan_tag: string;
  opponent_tag: string;
  opponent_name: string;
  state: string;
  team_size: number;
  attacks_per_member: number;
  preparation_start_time: string;
  start_time: string;
  end_time: string;
  clan_stars: number;
  clan_destruction_pct: number;
  opponent_stars: number;
  opponent_destruction_pct: number;
  result: string | null;
  updated_at: string;
}

export interface WarAttack {
  id: number;
  war_id: number;
  attacker_tag: string;
  defender_tag: string;
  stars: number;
  destruction_percentage: number;
  attack_order: number;
  duration: number | null;
}

export interface WarDetail extends War {
  attacks: WarAttack[];
}

export interface Raid {
  id: number;
  clan_tag: string;
  state: string;
  start_time: string;
  end_time: string;
  capital_total_loot: number;
  raids_completed: number;
  total_attacks: number;
  enemy_districts_destroyed: number;
  offensive_reward: number;
  defensive_reward: number;
  updated_at: string;
}

export interface RaidMember {
  id: number;
  raid_id: number;
  player_tag: string;
  name: string;
  attacks: number;
  attack_limit: number;
  bonus_attack_limit: number;
  capital_resources_looted: number;
}

export interface RaidDetail extends Raid {
  members: RaidMember[];
}

export interface TrackedClan {
  clan_tag: string;
  note: string | null;
  added_at: string;
  clans?: {
    name: string;
    badge_url: string;
    clan_level: number;
    members_count: number;
  } | null;
}

export interface TrackedPlayer {
  player_tag: string;
  note: string | null;
  added_at: string;
}

export interface LegendsLeaderboardEntry {
  rank: number;
  player_tag: string;
  name: string;
  attack_total: number;
  defense_total: number;
  net: number;
  initial_trophies: number;
  final_trophies: number;
}

export interface LegendsLeaderboard {
  data: LegendsLeaderboardEntry[];
  legends_day: string;
}

export interface LegendsBattle {
  id: number;
  player_tag: string;
  opponent_tag: string;
  opponent_name: string | null;
  is_attack: boolean;
  stars: number;
  destruction_pct: number;
  trophies: number;
  legends_day: string;
  first_seen_at: string;
}

export interface LegendsPlayerDetail {
  player_tag: string;
  player_name: string;
  current_trophies: number;
  legends_day: string;
  is_current_legends_day: boolean;
  attacks: LegendsBattle[];
  defenses: LegendsBattle[];
}
