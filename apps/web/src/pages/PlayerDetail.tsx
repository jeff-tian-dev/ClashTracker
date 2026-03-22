import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Box, Card, Flex, Grid, Heading, Text, Badge } from "@radix-ui/themes";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import { api, Player } from "../lib/api";
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

export function PlayerDetail() {
  const { tag } = useParams<{ tag: string }>();
  const [player, setPlayer] = useState<Player | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tag) return;
    api.player(decodeURIComponent(tag))
      .then(setPlayer)
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
        {player.is_always_tracked && (
          <Badge color="blue" variant="soft">
            Always tracked
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
    </Box>
  );
}
