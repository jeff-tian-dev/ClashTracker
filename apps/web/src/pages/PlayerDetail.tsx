import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Box, Card, Flex, Grid, Heading, Text, Badge } from "@radix-ui/themes";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import { api, Player, PlayerActivityResponse } from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Flex direction="column" gap="1">
      <Text size="1" color="gray">{label}</Text>
      <Text size="4" weight="bold">{value}</Text>
    </Flex>
  );
}

function bucketAttacksByLocalHour(attacks: { attacked_at: string }[]): number[] {
  const counts = Array.from({ length: 24 }, () => 0);
  for (const a of attacks) {
    const h = new Date(a.attacked_at).getHours();
    if (h >= 0 && h <= 23) counts[h]++;
  }
  return counts;
}

/** Days from earliest stored attack to now (client clock). API returns up to 7 days of rows. */
function formatAttackHistorySpanDays(attacks: { attacked_at: string }[]): string | null {
  if (attacks.length === 0) return null;
  const first = Math.min(...attacks.map((a) => new Date(a.attacked_at).getTime()));
  const days = (Date.now() - first) / 86_400_000;
  if (!Number.isFinite(days) || days < 0) return null;
  if (days < 0.1) return "<0.1";
  if (days < 10) return days.toFixed(1);
  return days.toFixed(0);
}

function ActivityHourChart({ attacks }: { attacks: { attacked_at: string }[] }) {
  const counts = bucketAttacksByLocalHour(attacks);
  const max = Math.max(...counts, 1);
  const total = counts.reduce((a, b) => a + b, 0);
  const spanDays = formatAttackHistorySpanDays(attacks);

  return (
    <Flex direction="column" gap="3">
      <div>
        <Flex align="baseline" gap="2" wrap="wrap" mb="1">
          <Text size="3" weight="bold" as="span">
            Attack activity (last 7 days)
          </Text>
          <Text size="1" color="gray" as="span" className="italic shrink-0">
            {spanDays != null
              ? `(${spanDays} days of data)`
              : "(no attacks logged yet in this window)"}
          </Text>
        </Flex>
        <Text size="2" color="gray" as="div">
          By hour of day in your local timezone. Each bar is attacks between that hour and :59. The chart can use up to 7 days;
          recently tracked players often have fewer days of history—sparse bars do not mean inactive.
        </Text>
      </div>
      {total === 0 ? (
        <Text size="2" color="gray">
          No attack timestamps yet. After ingestion records new battles from your battle log, hourly counts will appear here.
        </Text>
      ) : (
        <div
          className="flex items-stretch gap-0.5 sm:gap-1 w-full h-40 pt-2 border-t border-[var(--gray-6)]"
          role="img"
          aria-label={`Attacks by local hour, last 7 days. Total ${total}.`}
        >
          {counts.map((c, hour) => {
            const label = `${hour.toString().padStart(2, "0")}:00–${hour.toString().padStart(2, "0")}:59`;
            const tip = `${label}: ${c} ${c === 1 ? "attack" : "attacks"}`;
            return (
            <div
              key={hour}
              className="flex-1 min-w-0 flex flex-col items-center justify-end gap-1 min-h-0"
              title={tip}
            >
              <div
                className="flex-1 w-full min-h-0 flex flex-col justify-end items-center"
                title={tip}
              >
                <div
                  className="w-full max-w-[14px] mx-auto rounded-sm bg-[var(--accent-9)] opacity-90 hover:opacity-100 transition-opacity"
                  style={{
                    height: `${Math.max((c / max) * 100, c > 0 ? 8 : 0)}%`,
                    minHeight: c > 0 ? "4px" : undefined,
                  }}
                  title={tip}
                />
              </div>
              <Text
                size="1"
                color="gray"
                className="tabular-nums leading-none text-[9px] sm:text-[10px] w-full text-center truncate"
              >
                {hour.toString().padStart(2, "0")}
              </Text>
            </div>
            );
          })}
        </div>
      )}
    </Flex>
  );
}

export function PlayerDetail() {
  const { tag } = useParams<{ tag: string }>();
  const [player, setPlayer] = useState<Player | null>(null);
  const [activity, setActivity] = useState<PlayerActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tag) return;
    const decoded = decodeURIComponent(tag);
    setLoading(true);
    setError(null);
    Promise.all([
      api.player(decoded),
      api.playerActivity(decoded).catch(() => ({ attacks: [] as { attacked_at: string }[] })),
    ])
      .then(([p, act]) => {
        setPlayer(p);
        setActivity(act);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tag]);

  if (loading) return <LoadingSpinner />;
  if (error) return <EmptyState message={error} />;
  if (!player) return <EmptyState message="Player not found." />;

  return (
    <Box>
      <Link to="/players" className="inline-flex items-center gap-1 text-sm text-[var(--accent-11)] hover:underline mb-4">
        <ArrowLeftIcon /> Back to Players
      </Link>
      <Flex align="center" gap="3" mb="4" wrap="wrap">
        <Heading size="6">{player.name}</Heading>
        <Badge variant="outline">{player.tag}</Badge>
        {player.is_always_tracked && player.tracking_group === "external" && (
          <Badge color="amber" variant="soft">
            External
          </Badge>
        )}
        {player.is_always_tracked && player.tracking_group !== "external" && (
          <Badge color="blue" variant="soft">
            July
          </Badge>
        )}
        {player.left_tracked_roster_at && (
          <Badge color="gray" variant="surface">
            Not on tracked roster ({new Date(player.left_tracked_roster_at).toLocaleString()})
          </Badge>
        )}
      </Flex>
      <Card>
        <Grid columns={{ initial: "2", md: "4" }} gap="5" p="2">
          <Stat label="Town Hall" value={player.town_hall_level} />
          <Stat label="Experience" value={player.exp_level} />
          <Stat label="Trophies" value={player.trophies.toLocaleString()} />
          <Stat label="Best Trophies" value={player.best_trophies.toLocaleString()} />
          <Stat label="War Stars" value={player.war_stars} />
          <Stat label="Attack Wins" value={player.attack_wins} />
          <Stat label="Defense Wins" value={player.defense_wins} />
          <Stat label="Role" value={player.role || "—"} />
          <Stat label="War Preference" value={player.war_preference || "—"} />
          <Stat label="League" value={player.league_name || "—"} />
          <Stat label="Capital Contributions" value={player.clan_capital_contributions.toLocaleString()} />
          <Stat label="Last Updated" value={new Date(player.updated_at).toLocaleString()} />
          {player.left_tracked_roster_at && (
            <Stat
              label="Detected off tracked roster"
              value={new Date(player.left_tracked_roster_at).toLocaleString()}
            />
          )}
        </Grid>
      </Card>
      <Card mt="4">
        <Box p="4">
          <ActivityHourChart attacks={activity?.attacks ?? []} />
        </Box>
      </Card>
    </Box>
  );
}
