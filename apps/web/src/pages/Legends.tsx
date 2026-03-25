import { useEffect, useMemo, useState } from "react";
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
} from "@radix-ui/themes";
import {
  api,
  LegendsLeaderboardEntry,
  LegendsPlayerDetail,
  LegendsBattle,
} from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";
import { DIALOG_CONTENT_LG } from "../lib/dialogClasses";

/** Dedup archive days — not shown in the modal date picker (matches API filter). */
const HIDDEN_LEGENDS_DAYS = new Set(["2026-03-22"]);

function filterVisibleLegendsDays(days: string[]): string[] {
  return days.filter((d) => !HIDDEN_LEGENDS_DAYS.has(d));
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

type LegendsDisplayRow = {
  entry: LegendsLeaderboardEntry;
  rankShown: number;
  rankStruckThrough: boolean;
  julyMuted: boolean;
};

function buildLegendsDisplayRows(
  entries: LegendsLeaderboardEntry[],
  julyOnly: boolean,
): LegendsDisplayRow[] {
  if (!julyOnly) {
    return entries.map((entry) => ({
      entry,
      rankShown: entry.rank,
      rankStruckThrough: false,
      julyMuted: false,
    }));
  }
  const isJuly = (e: LegendsLeaderboardEntry) => Boolean(e.is_always_tracked);
  const july = entries.filter(isJuly).sort(compareLegendsTrophyOrder);
  const other = entries.filter((e) => !isJuly(e)).sort(compareLegendsTrophyOrder);
  const out: LegendsDisplayRow[] = [];
  july.forEach((entry, i) => {
    out.push({ entry, rankShown: i + 1, rankStruckThrough: false, julyMuted: false });
  });
  other.forEach((entry) => {
    out.push({
      entry,
      rankShown: entry.rank,
      rankStruckThrough: true,
      julyMuted: true,
    });
  });
  return out;
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
  const [entries, setEntries] = useState<LegendsLeaderboardEntry[]>([]);
  const [legendsDay, setLegendsDay] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [detail, setDetail] = useState<LegendsPlayerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [availableLegendsDays, setAvailableLegendsDays] = useState<string[]>([]);
  const [modalSelectedDay, setModalSelectedDay] = useState("");
  const [julyOnly, setJulyOnly] = useState(false);

  const displayRows = useMemo(
    () => buildLegendsDisplayRows(entries, julyOnly),
    [entries, julyOnly],
  );

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    api
      .legends()
      .then((res) => {
        setLoadError(null);
        setEntries(res.data);
        setLegendsDay(res.legends_day);
      })
      .catch((err: unknown) => {
        setEntries([]);
        setLegendsDay("");
        setLoadError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, []);

  async function openDetail(tag: string) {
    setSelectedTag(tag);
    setDetailLoading(true);
    setDetail(null);
    setAvailableLegendsDays([]);
    const initialDay = legendsDay || undefined;
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

  return (
    <Box>
      <Flex align="center" justify="between" gap="4" wrap="wrap" mb="4">
        <Flex align="baseline" gap="3" wrap="wrap">
          <Heading size="6">Legends League</Heading>
          {legendsDay && (
            <Text size="2" color="gray">
              Day: {legendsDay}
            </Text>
          )}
        </Flex>
        <label
          htmlFor="legends-july-only"
          className="inline-flex items-center gap-2 cursor-pointer touch-manipulation py-1"
        >
          <Text size="2" weight="medium">
            July only
          </Text>
          <Switch id="legends-july-only" size="2" checked={julyOnly} onCheckedChange={setJulyOnly} />
        </label>
      </Flex>
      {julyOnly && (
        <Text size="2" color="gray" mb="3" style={{ display: "block", maxWidth: 720 }}>
          July roster first (by final trophies). Everyone else is listed below with the full-leaderboard
          rank struck through.
        </Text>
      )}

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
        <EmptyState message="No players in Legends League in the roster yet." />
      ) : (
        <TableScrollArea>
          <Table.Root variant="surface" className="min-w-[640px]">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Attack</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Defense</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Net</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Initial</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Final</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {displayRows.map(({ entry: e, rankShown, rankStruckThrough, julyMuted }) => {
                const hasBattles = e.has_battles !== false;
                return (
              <Table.Row
                key={e.player_tag}
                className={
                  "cursor-pointer transition-colors hover:bg-[var(--gray-3)] [&_td]:!py-3 md:[&_td]:!py-2" +
                  (julyMuted ? " opacity-[0.55]" : "")
                }
                onClick={() => openDetail(e.player_tag)}
              >
                <Table.Cell>
                  <Text
                    weight="medium"
                    color={rankStruckThrough ? "gray" : undefined}
                    style={rankStruckThrough ? { textDecoration: "line-through" } : undefined}
                  >
                    {rankShown}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  <Text
                    className={
                      julyMuted ? "font-medium text-[var(--gray-11)]" : "text-[var(--accent-11)] font-medium"
                    }
                  >
                    {e.name}
                  </Text>
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
                    color={hasBattles ? (e.net > 0 ? "green" : e.net < 0 ? "red" : "gray") : "gray"}
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
              </Table.Row>
            );
            })}
            </Table.Body>
          </Table.Root>
        </TableScrollArea>
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
