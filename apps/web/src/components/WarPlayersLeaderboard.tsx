import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Badge,
  Box,
  Callout,
  Dialog,
  Flex,
  Select,
  Table,
  Text,
} from "@radix-ui/themes";
import { StarFilledIcon } from "@radix-ui/react-icons";
import {
  api,
  WarPlayerHistoryAttackRow,
  WarPlayerStatsEntry,
} from "../lib/api";
import { LoadingSpinner } from "./LoadingSpinner";
import { EmptyState } from "./EmptyState";
import { TableScrollArea } from "./TableScrollArea";
import {
  DIALOG_CONTENT_SCROLL_SAFE,
  DIALOG_MAX_W_WIDE,
} from "../lib/dialogClasses";

/** Deliberate low-effort hit (loot practice / dip). */
function isFarmingHit(
  stars: number | null | undefined,
  destructionPct: number | null | undefined,
): boolean {
  if (stars == null || destructionPct == null) return false;
  return stars === 1 && destructionPct < 40;
}

function Stars({ count }: { count: number }) {
  return (
    <Flex gap="1">
      {Array.from({ length: 3 }, (_, i) => (
        <StarFilledIcon
          key={i}
          color={i < count ? "var(--amber-9)" : "var(--gray-5)"}
        />
      ))}
    </Flex>
  );
}

function fmtAvg(v: number | null | undefined, suffix = ""): string {
  if (v == null) return "—";
  return `${v.toFixed(2)}${suffix}`;
}

const SORT_OPTIONS: { label: string; field: string; order: "asc" | "desc" }[] = [
  { label: "Avg stars / attack (high first)", field: "avg_offense_stars", order: "desc" },
  { label: "Avg stars / attack (low first)", field: "avg_offense_stars", order: "asc" },
  { label: "Avg destruction / attack (high first)", field: "avg_offense_destruction", order: "desc" },
  { label: "Avg destruction / attack (low first)", field: "avg_offense_destruction", order: "asc" },
  { label: "Attacks (most first)", field: "offense_count", order: "desc" },
  { label: "Attacks (fewest first)", field: "offense_count", order: "asc" },
  { label: "Attacks missed (most first)", field: "attacks_missed", order: "desc" },
  { label: "Attacks missed (fewest first)", field: "attacks_missed", order: "asc" },
  { label: "Avg defense stars (low first)", field: "avg_defense_stars", order: "asc" },
  { label: "Avg defense stars (high first)", field: "avg_defense_stars", order: "desc" },
  { label: "Avg defense destruction (low first)", field: "avg_defense_destruction", order: "asc" },
  { label: "Avg defense destruction (high first)", field: "avg_defense_destruction", order: "desc" },
  { label: "Defense count (most first)", field: "defense_count", order: "desc" },
  { label: "Wars participated (most first)", field: "wars_participated", order: "desc" },
  { label: "Name (A–Z)", field: "player_name", order: "asc" },
  { label: "Name (Z–A)", field: "player_name", order: "desc" },
];

function sortOptionValue(field: string, order: "asc" | "desc") {
  return `${field}:${order}`;
}

function parseSortOption(v: string): { field: string; order: "asc" | "desc" } {
  const [field, order] = v.split(":");
  return {
    field: field || "avg_offense_stars",
    order: order === "asc" ? "asc" : "desc",
  };
}

const PW_PARAM = "pw";

type WarWindow = "all" | 5 | 10 | 15;

function parseWarWindow(raw: string | null): WarWindow {
  if (raw === "5" || raw === "10" || raw === "15") return Number(raw) as 5 | 10 | 15;
  return "all";
}

function attackWindowApiArg(w: WarWindow): 5 | 10 | 15 | undefined {
  return w === "all" ? undefined : w;
}

function HistoryTable({
  title,
  rows,
  mode,
}: {
  title: string;
  rows: WarPlayerHistoryAttackRow[];
  mode: "offense" | "defense";
}) {
  if (rows.length === 0) {
    return (
      <Box mb="4">
        <Text weight="bold" size="3" mb="2" as="div">
          {title}
        </Text>
        <Text size="2" color="gray">
          No rows yet.
        </Text>
      </Box>
    );
  }

  return (
    <Box mb="4">
      <Text weight="bold" size="3" mb="2" as="div">
        {title} ({rows.length})
      </Text>
      <TableScrollArea>
        <Table.Root variant="surface" className="min-w-[680px]">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>War</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
              {mode === "offense" ? (
                <Table.ColumnHeaderCell>Defender</Table.ColumnHeaderCell>
              ) : (
                <Table.ColumnHeaderCell>Attacker</Table.ColumnHeaderCell>
              )}
              <Table.ColumnHeaderCell>Stars</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Destruction</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Duration</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Note</Table.ColumnHeaderCell>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {rows.map((r, idx) => {
              const missed = Boolean(r.missed_attack);
              const farming = !missed && isFarmingHit(r.stars, r.destruction_percentage);
              const rowMuted =
                farming || missed
                  ? "opacity-[0.72] [&_td]:text-[var(--gray-11)]"
                  : "";
              const linkClass =
                farming || missed
                  ? "text-[var(--gray-11)] hover:underline hover:text-[var(--gray-12)]"
                  : "text-[var(--accent-11)] hover:underline";
              return (
                <Table.Row key={`${r.war_id}-${r.attack_order}-${idx}`} className={rowMuted}>
                  <Table.Cell>
                    <Link to={`/wars/${r.war_id}`} className={linkClass}>
                      vs {r.opponent_name || "Unknown"}
                    </Link>
                  </Table.Cell>
                  <Table.Cell>
                    {r.start_time ? new Date(r.start_time).toLocaleDateString() : "—"}
                  </Table.Cell>
                  <Table.Cell>
                    {mode === "offense"
                      ? missed
                        ? "—"
                        : r.defender_tag
                      : r.attacker_tag}
                  </Table.Cell>
                  <Table.Cell>
                    {r.stars != null ? <Stars count={r.stars} /> : "—"}
                  </Table.Cell>
                  <Table.Cell>
                    {r.destruction_percentage != null
                      ? `${r.destruction_percentage.toFixed(1)}%`
                      : "—"}
                  </Table.Cell>
                  <Table.Cell>{r.duration != null ? `${r.duration}s` : "—"}</Table.Cell>
                  <Table.Cell>
                    {missed ? (
                      <Badge size="1" color="gray" variant="surface">
                        Missed attack
                      </Badge>
                    ) : farming ? (
                      <Badge size="1" color="gray" variant="surface">
                        Farming attack
                      </Badge>
                    ) : (
                      <Text size="2" color="gray">
                        —
                      </Text>
                    )}
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      </TableScrollArea>
    </Box>
  );
}

export function WarPlayersLeaderboard({ clanTag }: { clanTag: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  // Do not memoize on [searchParams]: RR keeps a stable URLSearchParams ref while hash query
  // updates, so the memo would never invalidate and pw would stay stuck (always "all").
  const warWindow = parseWarWindow(searchParams.get(PW_PARAM));

  const [entries, setEntries] = useState<WarPlayerStatsEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState(() =>
    sortOptionValue("avg_offense_stars", "desc"),
  );

  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [offenses, setOffenses] = useState<WarPlayerHistoryAttackRow[]>([]);
  const [defenses, setDefenses] = useState<WarPlayerHistoryAttackRow[]>([]);
  const [detailName, setDetailName] = useState("");

  const { field: sortField, order: sortOrder } = parseSortOption(sortKey);

  const loadLeaderboard = useCallback(() => {
    if (!clanTag) return;
    setLoading(true);
    setError(null);
    const la = attackWindowApiArg(warWindow);
    api
      .warPlayerStats({
        clan_tag: clanTag,
        sort: sortField,
        order: sortOrder,
        ...(la != null ? { last_attacks: la } : {}),
      })
      .then((res) => setEntries(res.data))
      .catch((err: unknown) => {
        setEntries([]);
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [clanTag, sortField, sortOrder, warWindow]);

  useEffect(() => {
    loadLeaderboard();
  }, [loadLeaderboard]);

  function openDetail(tag: string, name: string) {
    setSelectedTag(tag);
    setDetailName(name);
  }

  useEffect(() => {
    if (!selectedTag || !clanTag) return;
    let cancelled = false;
    setDetailLoading(true);
    setOffenses([]);
    setDefenses([]);
    const la = attackWindowApiArg(warWindow);
    api
      .warPlayerHistory(selectedTag, clanTag, la != null ? { last_attacks: la } : {})
      .then((res) => {
        if (!cancelled) {
          setOffenses(res.offenses);
          setDefenses(res.defenses);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOffenses([]);
          setDefenses([]);
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedTag, clanTag, warWindow]);

  if (!clanTag) {
    return <EmptyState message="Select a tracked clan to view player stats." />;
  }

  if (loading) return <LoadingSpinner />;
  if (error) {
    return (
      <Callout.Root color="red" role="alert">
        <Callout.Text weight="medium">Could not load war player stats.</Callout.Text>
        <Text size="2" color="gray" mt="1" as="p">
          {error}
        </Text>
      </Callout.Root>
    );
  }

  return (
    <Box>
      <Text size="1" color="gray" mb="3" as="p">
        Farming hits (1 star and under 40% destruction) are excluded from averages and attack counts.
        They still appear in history. Missed attacks appear in history and only affect the Missed column.
        When limited, stats and history use the player{"'"}s last N home offensive rows and last N
        defensive rows (by war date), separately.
      </Text>
      <Flex align="center" gap="3" wrap="wrap" mb="4">
        <Text size="2" weight="medium">
          Window
        </Text>
        <Select.Root
          value={warWindow === "all" ? "all" : String(warWindow)}
          onValueChange={(v) => {
            if (!v) return;
            setSearchParams(
              (prev) => {
                const n = new URLSearchParams(prev);
                if (v === "all") n.delete(PW_PARAM);
                else n.set(PW_PARAM, v);
                return n;
              },
              { replace: true },
            );
          }}
        >
          <Select.Trigger />
          <Select.Content position="popper">
            <Select.Item value="all">All offenses and defenses</Select.Item>
            <Select.Item value="5">Last 5 offenses and defenses</Select.Item>
            <Select.Item value="10">Last 10 offenses and defenses</Select.Item>
            <Select.Item value="15">Last 15 offenses and defenses</Select.Item>
          </Select.Content>
        </Select.Root>
        <Text size="2" weight="medium">
          Sort by
        </Text>
        <Select.Root
          value={sortKey}
          onValueChange={(v) => {
            if (v) setSortKey(v);
          }}
        >
          <Select.Trigger placeholder="Sort" />
          <Select.Content position="popper">
            {SORT_OPTIONS.map((o) => (
              <Select.Item
                key={sortOptionValue(o.field, o.order)}
                value={sortOptionValue(o.field, o.order)}
              >
                {o.label}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>

      {entries.length === 0 ? (
        <EmptyState message="No war player stats for this clan yet. Ended wars with synced attack data will appear here after ingestion." />
      ) : (
        <TableScrollArea>
          <Table.Root variant="surface" className="min-w-[920px]">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Player</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Avg stars / atk</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Avg dest / atk</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Attacks</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Missed</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Avg def %</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Avg def stars</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {entries.map((e, i) => (
                <Table.Row
                  key={e.player_tag}
                  className="cursor-pointer transition-colors hover:bg-[var(--gray-3)] [&_td]:!py-3 md:[&_td]:!py-2"
                  onClick={() => void openDetail(e.player_tag, e.player_name)}
                >
                  <Table.Cell>{i + 1}</Table.Cell>
                  <Table.Cell>
                    <Text weight="medium" className="text-[var(--accent-11)]">
                      {e.player_name}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>{fmtAvg(e.avg_offense_stars)}</Table.Cell>
                  <Table.Cell>{fmtAvg(e.avg_offense_destruction, "%")}</Table.Cell>
                  <Table.Cell>{e.offense_count}</Table.Cell>
                  <Table.Cell>{e.attacks_missed}</Table.Cell>
                  <Table.Cell>{fmtAvg(e.avg_defense_destruction, "%")}</Table.Cell>
                  <Table.Cell>{fmtAvg(e.avg_defense_stars)}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </TableScrollArea>
      )}

      <Dialog.Root
        open={selectedTag !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedTag(null);
            setOffenses([]);
            setDefenses([]);
            setDetailName("");
          }
        }}
      >
        <Dialog.Content
          maxWidth={DIALOG_MAX_W_WIDE}
          width="100%"
          className={DIALOG_CONTENT_SCROLL_SAFE}
        >
          {detailLoading && offenses.length === 0 && defenses.length === 0 ? (
            <>
              <Dialog.Title>War history</Dialog.Title>
              <LoadingSpinner />
            </>
          ) : (
            <>
              <Dialog.Title>{detailName || selectedTag}</Dialog.Title>
              <Dialog.Description size="2" color="gray" mb="3">
                War history for {selectedTag}
                {warWindow === "all"
                  ? " (all ended wars)"
                  : ` (last ${warWindow} offenses and last ${warWindow} defenses)`}
              </Dialog.Description>
              {detailLoading ? (
                <Text size="2" color="gray" mb="2">
                  Refreshing…
                </Text>
              ) : null}
              <HistoryTable
                title={warWindow === "all" ? "Offense" : `Offense (last ${warWindow})`}
                rows={offenses}
                mode="offense"
              />
              <HistoryTable
                title={warWindow === "all" ? "Defense" : `Defense (last ${warWindow})`}
                rows={defenses}
                mode="defense"
              />
            </>
          )}
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
