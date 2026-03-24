import { useEffect, useState } from "react";
import { Box, Heading, Table, Text, Dialog, Flex, Badge, Select } from "@radix-ui/themes";
import {
  api,
  LegendsLeaderboardEntry,
  LegendsPlayerDetail,
  LegendsBattle,
} from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

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

function BattleTable({ battles, type }: { battles: LegendsBattle[]; type: "attack" | "defense" }) {
  if (battles.length === 0) {
    return <Text size="2" color="gray">No {type === "attack" ? "attacks" : "defenses"} yet.</Text>;
  }

  return (
    <Table.Root variant="surface" size="1">
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
            <Table.Cell><Stars count={b.stars} /></Table.Cell>
            <Table.Cell>{b.destruction_pct}%</Table.Cell>
            <Table.Cell>
              <Text color={type === "attack" ? "green" : "red"} weight="medium">
                {type === "attack" ? "+" : "−"}{b.trophies}
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
  );
}

export function Legends() {
  const [entries, setEntries] = useState<LegendsLeaderboardEntry[]>([]);
  const [legendsDay, setLegendsDay] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [detail, setDetail] = useState<LegendsPlayerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [availableLegendsDays, setAvailableLegendsDays] = useState<string[]>([]);
  const [modalSelectedDay, setModalSelectedDay] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .legends()
      .then((res) => {
        setEntries(res.data);
        setLegendsDay(res.legends_day);
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
      <Flex align="baseline" gap="3" mb="4">
        <Heading size="6">Legends League</Heading>
        {legendsDay && (
          <Text size="2" color="gray">
            Day: {legendsDay}
          </Text>
        )}
      </Flex>

      {loading ? (
        <LoadingSpinner />
      ) : entries.length === 0 ? (
        <EmptyState message="No legends battles recorded for today." />
      ) : (
        <Table.Root variant="surface">
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
            {entries.map((e) => (
              <Table.Row
                key={e.player_tag}
                className="cursor-pointer hover:bg-[var(--gray-3)] transition-colors"
                onClick={() => openDetail(e.player_tag)}
              >
                <Table.Cell>
                  <Text weight="medium">{e.rank}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Text className="text-[var(--accent-11)] font-medium">{e.name}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Text color="green">+{e.attack_total}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Text color="red">−{e.defense_total}</Text>
                </Table.Cell>
                <Table.Cell>
                  <Badge
                    size="1"
                    color={e.net > 0 ? "green" : e.net < 0 ? "red" : "gray"}
                    variant="soft"
                  >
                    {e.net > 0 ? "+" : ""}{e.net}
                  </Badge>
                </Table.Cell>
                <Table.Cell>{e.initial_trophies.toLocaleString()}</Table.Cell>
                <Table.Cell>
                  <Text weight="medium">{e.final_trophies.toLocaleString()}</Text>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
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
        <Dialog.Content maxWidth="600px">
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
