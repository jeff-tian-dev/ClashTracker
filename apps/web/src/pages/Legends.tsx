import { Fragment, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Box,
  Heading,
  Table,
  Text,
  Dialog,
  Flex,
  Badge,
  Select,
  Callout,
  Switch,
  IconButton,
  Button,
} from "@radix-ui/themes";
import { TrashIcon } from "@radix-ui/react-icons";
import {
  api,
  LegendsLeaderboardEntry,
  LegendsPlayerDetail,
  LegendsBattle,
} from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";
import { DIALOG_CONTENT_LG, DIALOG_CONTENT_SM } from "../lib/dialogClasses";
import { formatLeftAgo } from "../lib/formatRelativeLeft";
import { useAdmin } from "../lib/AdminContext";

/** Dedup archive days — not shown in the modal date picker (matches API filter). */
const HIDDEN_LEGENDS_DAYS = new Set(["2026-03-22"]);

function filterVisibleLegendsDays(days: string[]): string[] {
  return days.filter((d) => !HIDDEN_LEGENDS_DAYS.has(d));
}

function formatBattleSeenAt(iso: string | undefined): string {
  if (iso == null || iso === "") return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString();
}

function Stars({ count }: { count: number }) {
  return (
    <Flex gap="1" align="center">
      {Array.from({ length: 3 }, (_, i) => (
        <Text key={i} size="2" style={{ color: i < count ? "#f59e0b" : "var(--gray-6)" }}>
          ★
        </Text>
      ))}
    </Flex>
  );
}

function compareLegendsTrophyOrder(a: LegendsLeaderboardEntry, b: LegendsLeaderboardEntry) {
  if (b.final_trophies !== a.final_trophies) return b.final_trophies - a.final_trophies;
  return b.net - a.net;
}

function isLeftRosterDemoted(e: LegendsLeaderboardEntry): boolean {
  return Boolean(e.left_tracked_roster_at) && !e.is_always_tracked;
}

/** Non-tracked players who left tracked roster: bottom of section; then by leave time (Players tab order). */
function compareLegendsDisplayOrder(a: LegendsLeaderboardEntry, b: LegendsLeaderboardEntry): number {
  const aDem = isLeftRosterDemoted(a);
  const bDem = isLeftRosterDemoted(b);
  if (aDem !== bDem) return aDem ? 1 : -1;
  if (aDem && bDem) {
    const ta = new Date(a.left_tracked_roster_at!).getTime();
    const tb = new Date(b.left_tracked_roster_at!).getTime();
    if (tb !== ta) return tb - ta;
    return a.name.localeCompare(b.name);
  }
  return compareLegendsTrophyOrder(a, b);
}

/** Primary block in “July only” view: clan (July) list, not external pins. */
function isClanJulyPrimary(e: LegendsLeaderboardEntry): boolean {
  if (e.tracking_group === "clan_july") return true;
  if (e.tracking_group === "external") return false;
  return Boolean(e.is_always_tracked);
}

type LegendsDisplayRow = {
  entry: LegendsLeaderboardEntry;
  rankLabel: string;
  julyMuted: boolean;
};

type LegendsDisplayBlock = {
  heading: string | null;
  rows: LegendsDisplayRow[];
};

function buildLegendsDisplayBlocks(
  entries: LegendsLeaderboardEntry[],
  julyOnly: boolean,
  aprilPush: boolean,
): LegendsDisplayBlock[] {
  if (!julyOnly) {
    const sorted = [...entries].sort(compareLegendsDisplayOrder);
    return [
      {
        heading: null,
        rows: sorted.map((entry, i) => ({
          entry,
          rankLabel: String(i + 1),
          julyMuted: false,
        })),
      },
    ];
  }

  if (!aprilPush) {
    const rows: LegendsDisplayRow[] = [];
    const clanJuly = entries.filter(isClanJulyPrimary).sort(compareLegendsDisplayOrder);
    const other = entries.filter((e) => !isClanJulyPrimary(e)).sort(compareLegendsDisplayOrder);
    clanJuly.forEach((entry, i) => {
      rows.push({ entry, rankLabel: String(i + 1), julyMuted: false });
    });
    other.forEach((entry) => {
      rows.push({ entry, rankLabel: "—", julyMuted: true });
    });
    return [{ heading: null, rows }];
  }

  const primary = entries.filter(isClanJulyPrimary);
  const upper = primary
    .filter((e) => (e.legends_bracket ?? 1) === 1)
    .sort(compareLegendsDisplayOrder);
  const lower = primary
    .filter((e) => (e.legends_bracket ?? 1) === 2)
    .sort(compareLegendsDisplayOrder);
  const other = entries.filter((e) => !isClanJulyPrimary(e)).sort(compareLegendsDisplayOrder);

  const blocks: LegendsDisplayBlock[] = [
    {
      heading: "Upper bracket",
      rows: upper.map((entry, i) => ({
        entry,
        rankLabel: String(i + 1),
        julyMuted: false,
      })),
    },
    {
      heading: "Lower bracket",
      rows: lower.map((entry, i) => ({
        entry,
        rankLabel: String(i + 1),
        julyMuted: false,
      })),
    },
  ];
  if (other.length > 0) {
    blocks.push({
      heading: null,
      rows: other.map((entry) => ({
        entry,
        rankLabel: "—",
        julyMuted: true,
      })),
    });
  }
  return blocks;
}

function tieBreakWinner(a: LegendsLeaderboardEntry, b: LegendsLeaderboardEntry): LegendsLeaderboardEntry {
  if (a.final_trophies !== b.final_trophies) {
    return a.final_trophies > b.final_trophies ? a : b;
  }
  return a.name.localeCompare(b.name) <= 0 ? a : b;
}

function pickMaxMetric(
  pool: LegendsLeaderboardEntry[],
  metric: (e: LegendsLeaderboardEntry) => number,
): LegendsLeaderboardEntry | null {
  if (pool.length === 0) return null;
  return pool.reduce((best, e) => {
    const me = metric(e);
    const mb = metric(best);
    if (me !== mb) return me > mb ? e : best;
    return tieBreakWinner(e, best);
  });
}

function pickMinMetric(
  pool: LegendsLeaderboardEntry[],
  metric: (e: LegendsLeaderboardEntry) => number,
): LegendsLeaderboardEntry | null {
  if (pool.length === 0) return null;
  return pool.reduce((best, e) => {
    const me = metric(e);
    const mb = metric(best);
    if (me !== mb) return me < mb ? e : best;
    return tieBreakWinner(e, best);
  });
}

type LegendsDayLeaders = {
  bestAttacks: LegendsLeaderboardEntry | null;
  highestNet: LegendsLeaderboardEntry | null;
  bestDefense: LegendsLeaderboardEntry | null;
  bestBase: LegendsLeaderboardEntry | null;
  bestBaseAvg: number | null;
};

function computeLegendsDayLeaders(
  entries: LegendsLeaderboardEntry[],
  julyOnly: boolean,
): LegendsDayLeaders {
  const pool = julyOnly ? entries.filter(isClanJulyPrimary) : entries;
  const candidates = pool.filter((e) => !isLeftRosterDemoted(e));
  const hasBattles = (e: LegendsLeaderboardEntry) => e.has_battles !== false;

  const bestAttacks = pickMaxMetric(
    candidates.filter((e) => hasBattles(e) && e.attack_battle_count > 0),
    (e) => e.attack_total,
  );
  const highestNet = pickMaxMetric(candidates.filter(hasBattles), (e) => e.net);

  const withDefense = candidates.filter((e) => e.defense_battle_count > 0);
  const bestDefense = pickMinMetric(withDefense, (e) => e.defense_total);
  const bestBase = pickMinMetric(withDefense, (e) => e.defense_total / e.defense_battle_count);
  const bestBaseAvg = bestBase ? bestBase.defense_total / bestBase.defense_battle_count : null;

  return { bestAttacks, highestNet, bestDefense, bestBase, bestBaseAvg };
}

function StatHighlight({
  label,
  name,
  value,
  onOpen,
}: {
  label: string;
  name: string;
  value: ReactNode;
  onOpen?: () => void;
}) {
  const interactive = Boolean(onOpen);
  return (
    <Box
      style={{ minWidth: 140, flex: "1 1 140px" }}
      className={
        interactive
          ? "cursor-pointer rounded-[var(--radius-2)] p-2 -m-2 transition-colors hover:bg-[var(--gray-3)]"
          : undefined
      }
      onClick={onOpen}
      onKeyDown={
        interactive
          ? (ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                onOpen?.();
              }
            }
          : undefined
      }
      tabIndex={interactive ? 0 : undefined}
      role={interactive ? "button" : undefined}
    >
      <Text size="1" color="gray" weight="medium" mb="1" as="div">
        {label}
      </Text>
      <Text size="2" weight="bold" className="text-[var(--accent-11)]" as="div">
        {name}
      </Text>
      <Box mt="1">{value}</Box>
    </Box>
  );
}

function LegendsLeaderboardTable({
  displayBlocks,
  isAdmin,
  openDetail,
  handleDeletePlayer,
}: {
  displayBlocks: LegendsDisplayBlock[];
  isAdmin: boolean;
  openDetail: (tag: string) => void;
  handleDeletePlayer: (tag: string) => void;
}) {
  const colSpan = isAdmin ? 8 : 7;
  return (
    <TableScrollArea>
      <Table.Root variant="surface" className="min-w-[700px]">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Attack</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Defense</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Net</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Initial</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Final</Table.ColumnHeaderCell>
            {isAdmin && <Table.ColumnHeaderCell />}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {displayBlocks.map((block, blockIdx) => (
            <Fragment key={block.heading ?? `block-${blockIdx}`}>
              {block.heading ? (
                <Table.Row>
                  <Table.Cell colSpan={colSpan}>
                    <Heading size="3">{block.heading}</Heading>
                  </Table.Cell>
                </Table.Row>
              ) : null}
              {block.rows.length === 0 && block.heading ? (
                <Table.Row>
                  <Table.Cell colSpan={colSpan}>
                    <Text size="2" color="gray">
                      No players in this bracket.
                    </Text>
                  </Table.Cell>
                </Table.Row>
              ) : null}
              {block.rows.map(({ entry: e, rankLabel, julyMuted }) => {
                const hasBattles = e.has_battles !== false;
                const leftDemoted = isLeftRosterDemoted(e);
                const rowMuted = leftDemoted ? " opacity-60" : julyMuted ? " opacity-[0.55]" : "";
                const nameGrey = julyMuted || leftDemoted;
                return (
                  <Table.Row
                    key={e.player_tag}
                    className={
                      "cursor-pointer transition-colors hover:bg-[var(--gray-3)] [&_td]:!py-3 md:[&_td]:!py-2" +
                      rowMuted
                    }
                    onClick={() => openDetail(e.player_tag)}
                  >
                    <Table.Cell>
                      <Text weight="medium" color={julyMuted ? "gray" : undefined}>
                        {rankLabel}
                      </Text>
                    </Table.Cell>
                    <Table.Cell>
                      <Flex gap="2" wrap="wrap" align="center">
                        <Text
                          className={
                            nameGrey
                              ? "font-medium text-[var(--gray-11)]"
                              : "text-[var(--accent-11)] font-medium"
                          }
                        >
                          {e.name}
                        </Text>
                        {leftDemoted && e.left_tracked_roster_at ? (
                          <Badge size="1" color="gray" variant="surface">
                            {formatLeftAgo(e.left_tracked_roster_at)}
                          </Badge>
                        ) : null}
                      </Flex>
                    </Table.Cell>
                    <Table.Cell>
                      {hasBattles ? (
                        <Text color="green">+{e.attack_total}</Text>
                      ) : (
                        <Text size="2" color="gray">
                          —
                        </Text>
                      )}
                    </Table.Cell>
                    <Table.Cell>
                      {hasBattles ? (
                        <Text color="red">−{e.defense_total}</Text>
                      ) : (
                        <Text size="2" color="gray">
                          —
                        </Text>
                      )}
                    </Table.Cell>
                    <Table.Cell>
                      <Badge
                        size="1"
                        color={
                          hasBattles ? (e.net > 0 ? "green" : e.net < 0 ? "red" : "gray") : "gray"
                        }
                        variant="soft"
                      >
                        {hasBattles ? (
                          <>
                            {e.net > 0 ? "+" : ""}
                            {e.net}
                          </>
                        ) : (
                          "—"
                        )}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>{e.initial_trophies.toLocaleString()}</Table.Cell>
                    <Table.Cell>
                      <Text weight="medium">{e.final_trophies.toLocaleString()}</Text>
                    </Table.Cell>
                    {isAdmin && (
                      <Table.Cell
                        onClick={(ev) => ev.stopPropagation()}
                        onKeyDown={(ev) => ev.stopPropagation()}
                      >
                        <Dialog.Root>
                          <Dialog.Trigger>
                            <IconButton
                              type="button"
                              variant="ghost"
                              color="red"
                              size={{ initial: "2", md: "1" }}
                              aria-label="Delete player"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              <TrashIcon />
                            </IconButton>
                          </Dialog.Trigger>
                          <Dialog.Content className={DIALOG_CONTENT_SM}>
                            <Dialog.Title>Delete player</Dialog.Title>
                            <Dialog.Description>
                              Remove {e.name} ({e.player_tag}) from the dashboard? This deletes their row
                              and any Tracked Players pin, same as on the Players tab. They can show up
                              again after sync if they are still in a tracked clan.
                            </Dialog.Description>
                            <Flex
                              gap="3"
                              mt="4"
                              justify="end"
                              direction={{ initial: "column", sm: "row" }}
                              wrap="wrap"
                            >
                              <Dialog.Close>
                                <Button variant="soft" color="gray">
                                  Cancel
                                </Button>
                              </Dialog.Close>
                              <Dialog.Close>
                                <Button color="red" onClick={() => handleDeletePlayer(e.player_tag)}>
                                  Delete
                                </Button>
                              </Dialog.Close>
                            </Flex>
                          </Dialog.Content>
                        </Dialog.Root>
                      </Table.Cell>
                    )}
                  </Table.Row>
                );
              })}
            </Fragment>
          ))}
        </Table.Body>
      </Table.Root>
    </TableScrollArea>
  );
}

function BattleTable({ battles, type }: { battles: LegendsBattle[]; type: "attack" | "defense" }) {
  if (battles.length === 0) {
    return <Text size="2" color="gray">No {type === "attack" ? "attacks" : "defenses"} yet.</Text>;
  }

  return (
    <TableScrollArea inset={false}>
      <Table.Root variant="surface" size="1" className="min-w-[520px]">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Opponent</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Stars</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Destruction</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Trophies</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Time</Table.ColumnHeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {battles.map((b) => (
            <Table.Row key={b.id}>
              <Table.Cell>{b.opponent_name || b.opponent_tag}</Table.Cell>
              <Table.Cell>
                <Stars count={b.stars} />
              </Table.Cell>
              <Table.Cell>{b.destruction_pct}%</Table.Cell>
              <Table.Cell>
                <Text color={type === "attack" ? "green" : "red"} weight="medium">
                  {type === "attack" ? "+" : "−"}
                  {b.trophies}
                </Text>
              </Table.Cell>
              <Table.Cell>
                <Text size="1" color="gray">
                  {new Date(b.first_seen_at).toLocaleTimeString()}
                </Text>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </TableScrollArea>
  );
}

export function Legends() {
  const { isAdmin, adminKey } = useAdmin();
  const [entries, setEntries] = useState<LegendsLeaderboardEntry[]>([]);
  const [legendsDay, setLegendsDay] = useState("");
  const [currentLegendsDay, setCurrentLegendsDay] = useState("");
  const [selectedDay, setSelectedDay] = useState("");
  const [leaderboardDays, setLeaderboardDays] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [detail, setDetail] = useState<LegendsPlayerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [availableLegendsDays, setAvailableLegendsDays] = useState<string[]>([]);
  const [modalSelectedDay, setModalSelectedDay] = useState("");
  const [julyOnly, setJulyOnly] = useState(false);
  const [aprilPush, setAprilPush] = useState(false);

  const isViewingPastDay = selectedDay !== "" && selectedDay !== currentLegendsDay;

  const displayBlocks = useMemo(
    () => buildLegendsDisplayBlocks(entries, julyOnly, aprilPush),
    [entries, julyOnly, aprilPush],
  );

  const dayLeaders = useMemo(
    () => computeLegendsDayLeaders(entries, julyOnly),
    [entries, julyOnly],
  );

  useEffect(() => {
    // Initial load: fetch leaderboard for today + the season's day list in parallel.
    setLoading(true);
    setLoadError(null);
    let cancelled = false;
    Promise.all([api.legends(), api.legendsDays()])
      .then(([res, daysRes]) => {
        if (cancelled) return;
        setLoadError(null);
        setEntries(res.data);
        setLegendsDay(res.legends_day);
        setCurrentLegendsDay(res.legends_day);
        setSelectedDay(res.legends_day);
        const visible = filterVisibleLegendsDays(
          Array.from(new Set([res.legends_day, ...daysRes.legends_days])).sort((a, b) =>
            b.localeCompare(a),
          ),
        );
        setLeaderboardDays(visible);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setEntries([]);
        setLegendsDay("");
        setLeaderboardDays([]);
        setLoadError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleLeaderboardDayChange(day: string) {
    if (day === selectedDay) return;
    setSelectedDay(day);
    setLoading(true);
    setLoadError(null);
    api
      .legends(day)
      .then((res) => {
        setLoadError(null);
        setEntries(res.data);
        setLegendsDay(res.legends_day);
      })
      .catch((err: unknown) => {
        setEntries([]);
        setLoadError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }

  async function openDetail(tag: string) {
    setSelectedTag(tag);
    setDetailLoading(true);
    setDetail(null);
    setAvailableLegendsDays([]);
    const initialDay = selectedDay || legendsDay || undefined;
    if (initialDay) setModalSelectedDay(initialDay);
    try {
      const [daysRes, detailRes] = await Promise.all([
        api.legendsPlayerDays(tag),
        api.legendsPlayer(tag, initialDay),
      ]);
      const merged = filterVisibleLegendsDays(
        Array.from(
          new Set([...(initialDay ? [initialDay] : []), ...daysRes.legends_days])
        ).sort((a, b) => b.localeCompare(a))
      );
      if (merged.length === 0 && detailRes.legends_day && !HIDDEN_LEGENDS_DAYS.has(detailRes.legends_day)) {
        merged.push(detailRes.legends_day);
      }
      setAvailableLegendsDays(merged);
      setDetail(detailRes);
      setModalSelectedDay(detailRes.legends_day);
    } finally {
      setDetailLoading(false);
    }
  }

  function handleModalDayChange(day: string) {
    if (!selectedTag || day === modalSelectedDay) return;
    setModalSelectedDay(day);
    setDetailLoading(true);
    api
      .legendsPlayer(selectedTag, day)
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  }

  async function handleDeletePlayer(tag: string) {
    if (!adminKey) return;
    try {
      await api.deletePlayer(tag, adminKey);
      setEntries((prev) => prev.filter((e) => e.player_tag !== tag));
      if (selectedTag === tag) {
        setSelectedTag(null);
        setDetail(null);
        setAvailableLegendsDays([]);
        setModalSelectedDay("");
      }
    } catch (err) {
      console.error("Failed to delete player", err);
    }
  }

  return (
    <Box>
      <Flex align="center" justify="between" gap="4" wrap="wrap" mb="4">
        <Flex align="center" gap="3" wrap="wrap">
          <Heading size="6">Legends League</Heading>
          {leaderboardDays.length > 0 ? (
            <Flex align="center" gap="2">
              <Text size="2" color="gray">
                Day
              </Text>
              <Select.Root
                value={selectedDay}
                onValueChange={handleLeaderboardDayChange}
                disabled={loading}
              >
                <Select.Trigger placeholder="Select day" />
                <Select.Content position="popper">
                  {leaderboardDays.map((d) => (
                    <Select.Item key={d} value={d}>
                      {d === currentLegendsDay ? `${d} (today)` : d}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Flex>
          ) : legendsDay ? (
            <Text size="2" color="gray">
              Day: {legendsDay}
            </Text>
          ) : null}
          {isViewingPastDay && (
            <Text size="2" color="gray">
              Viewing past legends day
            </Text>
          )}
        </Flex>
        <Flex align="center" gap="4" wrap="wrap">
          <label
            htmlFor="legends-july-only"
            className="inline-flex items-center gap-2 cursor-pointer touch-manipulation py-1"
          >
            <Text size="2" weight="medium">
              July only
            </Text>
            <Switch
              id="legends-july-only"
              size="2"
              checked={julyOnly}
              onCheckedChange={(v) => {
                if (!v) setAprilPush(false);
                setJulyOnly(v);
              }}
            />
          </label>
          <label
            htmlFor="legends-april-push"
            className="inline-flex items-center gap-2 cursor-pointer touch-manipulation py-1"
          >
            <Text size="2" weight="medium">
              April push
            </Text>
            <Switch
              id="legends-april-push"
              size="2"
              checked={aprilPush}
              onCheckedChange={(v) => {
                if (v) setJulyOnly(true);
                setAprilPush(v);
              }}
            />
          </label>
        </Flex>
      </Flex>

      {!loading && !loadError && entries.length > 0 ? (
        <Flex
          wrap="wrap"
          gap="4"
          mb="4"
          className="rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-[var(--color-surface)] p-3 md:p-4"
        >
          <StatHighlight
            label="Best attacks"
            name={dayLeaders.bestAttacks?.name ?? "—"}
            value={
              dayLeaders.bestAttacks != null ? (
                <Text color="green" weight="medium">
                  +{dayLeaders.bestAttacks.attack_total.toLocaleString()}
                </Text>
              ) : (
                <Text color="gray">—</Text>
              )
            }
            onOpen={
              dayLeaders.bestAttacks ? () => void openDetail(dayLeaders.bestAttacks!.player_tag) : undefined
            }
          />
          <StatHighlight
            label="Highest net"
            name={dayLeaders.highestNet?.name ?? "—"}
            value={
              dayLeaders.highestNet != null ? (
                <Badge
                  size="1"
                  color={
                    dayLeaders.highestNet.net > 0
                      ? "green"
                      : dayLeaders.highestNet.net < 0
                        ? "red"
                        : "gray"
                  }
                  variant="soft"
                >
                  {dayLeaders.highestNet.net > 0 ? "+" : ""}
                  {dayLeaders.highestNet.net.toLocaleString()}
                </Badge>
              ) : (
                <Text color="gray">—</Text>
              )
            }
            onOpen={
              dayLeaders.highestNet ? () => void openDetail(dayLeaders.highestNet!.player_tag) : undefined
            }
          />
          <StatHighlight
            label="Best defense"
            name={dayLeaders.bestDefense?.name ?? "—"}
            value={
              dayLeaders.bestDefense != null ? (
                <Text color="red" weight="medium">
                  −{dayLeaders.bestDefense.defense_total.toLocaleString()}
                </Text>
              ) : (
                <Text color="gray">—</Text>
              )
            }
            onOpen={
              dayLeaders.bestDefense ? () => void openDetail(dayLeaders.bestDefense!.player_tag) : undefined
            }
          />
          <StatHighlight
            label="Best base"
            name={dayLeaders.bestBase?.name ?? "—"}
            value={
              dayLeaders.bestBaseAvg != null ? (
                <Text color="red" weight="medium">
                  {`−${dayLeaders.bestBaseAvg.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}/defense`}
                </Text>
              ) : (
                <Text color="gray">—</Text>
              )
            }
            onOpen={dayLeaders.bestBase ? () => void openDetail(dayLeaders.bestBase!.player_tag) : undefined}
          />
        </Flex>
      ) : null}

      {loading ? (
        <LoadingSpinner />
      ) : loadError ? (
        <Callout.Root color="red" role="alert">
          <Callout.Text weight="medium">Could not load the Legends leaderboard.</Callout.Text>
          <Text size="2" color="gray" mt="1" as="p">
            {loadError}
          </Text>
        </Callout.Root>
      ) : entries.length === 0 ? (
        <EmptyState
          message={
            isViewingPastDay
              ? `No Legends battles recorded for ${selectedDay}.`
              : "No players in Legends League in the roster yet."
          }
        />
      ) : (
        <LegendsLeaderboardTable
          displayBlocks={displayBlocks}
          isAdmin={isAdmin}
          openDetail={openDetail}
          handleDeletePlayer={handleDeletePlayer}
        />
      )}

      <Dialog.Root
        open={selectedTag !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedTag(null);
            setAvailableLegendsDays([]);
            setModalSelectedDay("");
          }
        }}
      >
        <Dialog.Content className={DIALOG_CONTENT_LG}>
          {detailLoading && !detail ? (
            <LoadingSpinner />
          ) : detail ? (
            <>
              <Dialog.Title>{detail.player_name}</Dialog.Title>

              {availableLegendsDays.length > 0 && (
                <Flex align="center" gap="3" mb="3" wrap="wrap">
                  <Text size="2" weight="medium">
                    Legends day
                  </Text>
                  <Select.Root
                    value={modalSelectedDay}
                    onValueChange={handleModalDayChange}
                    disabled={detailLoading}
                  >
                    <Select.Trigger placeholder="Select day" />
                    <Select.Content position="popper">
                      {availableLegendsDays.map((d) => (
                        <Select.Item key={d} value={d}>
                          {d}
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Root>
                </Flex>
              )}

              <Dialog.Description size="2" color="gray" mb="4">
                {detail.is_current_legends_day ? (
                  <>
                    {detail.current_trophies.toLocaleString()} trophies — {detail.legends_day}
                  </>
                ) : (
                  <>
                    Viewing past legends day ({detail.legends_day}). Profile trophy count is your
                    current live value, not end-of-that-day.
                  </>
                )}
              </Dialog.Description>

              {detailLoading ? (
                <Flex justify="center" py="3">
                  <LoadingSpinner />
                </Flex>
              ) : null}

              <Flex direction="column" gap="4" style={{ opacity: detailLoading ? 0.5 : 1 }}>
                <Box>
                  <Heading size="3" mb="2">
                    Attacks ({detail.attacks.length}/8)
                  </Heading>
                  <BattleTable battles={detail.attacks} type="attack" />
                </Box>
                <Box>
                  <Heading size="3" mb="2">
                    Defenses ({detail.defenses.length}/8)
                  </Heading>
                  <BattleTable battles={detail.defenses} type="defense" />
                </Box>
              </Flex>
            </>
          ) : null}
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
