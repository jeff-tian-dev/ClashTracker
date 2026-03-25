import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Box, Card, Flex, Grid, Heading, Text, Table, Badge } from "@radix-ui/themes";
import { api, DashboardData } from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <Flex direction="column" gap="1">
        <Text size="2" color="gray">
          {label}
        </Text>
        <Text size="7" weight="bold">
          {value}
        </Text>
      </Flex>
    </Card>
  );
}

function resultBadge(result: string | null) {
  if (!result) return <Badge color="gray">Ongoing</Badge>;
  if (result === "win") return <Badge color="green">Win</Badge>;
  if (result === "lose") return <Badge color="red">Loss</Badge>;
  return <Badge color="yellow">Tie</Badge>;
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <EmptyState message={error} />;
  if (!data) return <EmptyState message="No data available." />;

  return (
    <Box>
      <Heading size="6" mb="4">
        Dashboard
      </Heading>

      <Grid columns={{ initial: "2", md: "5" }} gap="4" mb="6">
        <StatCard label="Clans" value={data.total_clans} />
        <StatCard label="Players" value={data.total_players} />
        <StatCard label="Total Wars" value={data.total_wars} />
        <StatCard label="Active Wars" value={data.active_wars} />
        <StatCard label="Raid Seasons" value={data.total_raids} />
      </Grid>

      <Grid columns={{ initial: "1", md: "2" }} gap="6">
        <Box>
          <Heading size="4" mb="3">
            Recent Wars
          </Heading>
          {data.recent_wars.length === 0 ? (
            <EmptyState message="No wars recorded yet." />
          ) : (
            <TableScrollArea>
              <Table.Root variant="surface">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeaderCell>Opponent</Table.ColumnHeaderCell>
                    <Table.ColumnHeaderCell>Stars</Table.ColumnHeaderCell>
                    <Table.ColumnHeaderCell>Result</Table.ColumnHeaderCell>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {data.recent_wars.map((w) => (
                    <Table.Row key={w.id}>
                      <Table.Cell>
                        <Link to={`/wars/${w.id}`} className="text-[var(--accent-11)] hover:underline">
                          {w.opponent_name || "Unknown"}
                        </Link>
                      </Table.Cell>
                      <Table.Cell>
                        {w.clan_stars} - {w.opponent_stars}
                      </Table.Cell>
                      <Table.Cell>{resultBadge(w.result)}</Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </TableScrollArea>
          )}
        </Box>

        <Box>
          <Heading size="4" mb="3">
            Recent Raids
          </Heading>
          {data.recent_raids.length === 0 ? (
            <EmptyState message="No raids recorded yet." />
          ) : (
            <TableScrollArea>
              <Table.Root variant="surface">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeaderCell>Date</Table.ColumnHeaderCell>
                    <Table.ColumnHeaderCell>Loot</Table.ColumnHeaderCell>
                    <Table.ColumnHeaderCell>Raids</Table.ColumnHeaderCell>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {data.recent_raids.map((r) => (
                    <Table.Row key={r.id}>
                      <Table.Cell>
                        <Link to={`/raids/${r.id}`} className="text-[var(--accent-11)] hover:underline">
                          {new Date(r.start_time).toLocaleDateString()}
                        </Link>
                      </Table.Cell>
                      <Table.Cell>{r.capital_total_loot.toLocaleString()}</Table.Cell>
                      <Table.Cell>{r.raids_completed}</Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </TableScrollArea>
          )}
        </Box>
      </Grid>
    </Box>
  );
}
