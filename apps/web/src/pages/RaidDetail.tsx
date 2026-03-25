import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Box, Card, Flex, Heading, Text, Table } from "@radix-ui/themes";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import { api, RaidDetail as RaidDetailType } from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";

export function RaidDetail() {
  const { id } = useParams<{ id: string }>();
  const [raid, setRaid] = useState<RaidDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.raid(Number(id))
      .then(setRaid)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (error) return <EmptyState message={error} />;
  if (!raid) return <EmptyState message="Raid not found." />;

  return (
    <Box>
      <Link to="/raids" className="inline-flex items-center gap-1 text-sm text-[var(--accent-11)] hover:underline mb-4">
        <ArrowLeftIcon /> Back to Raids
      </Link>
      <Heading size="6" mb="4">
        Raid: {new Date(raid.start_time).toLocaleDateString()} — {new Date(raid.end_time).toLocaleDateString()}
      </Heading>

      <Card mb="5">
        <Flex gap="6" wrap="wrap" p="2">
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Total Loot</Text>
            <Text weight="bold">{raid.capital_total_loot.toLocaleString()}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Raids Completed</Text>
            <Text weight="bold">{raid.raids_completed}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Total Attacks</Text>
            <Text weight="bold">{raid.total_attacks}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Districts Destroyed</Text>
            <Text weight="bold">{raid.enemy_districts_destroyed}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Offensive Reward</Text>
            <Text weight="bold">{raid.offensive_reward}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Defensive Reward</Text>
            <Text weight="bold">{raid.defensive_reward}</Text>
          </Flex>
        </Flex>
      </Card>

      <Heading size="4" mb="3">
        Members ({raid.members.length})
      </Heading>

      {raid.members.length === 0 ? (
        <EmptyState message="No member data available." />
      ) : (
        <TableScrollArea>
          <Table.Root variant="surface" className="min-w-[480px]">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Attacks</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Limit</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Loot</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {raid.members.map((m) => (
                <Table.Row key={m.id}>
                  <Table.Cell>{m.name}</Table.Cell>
                  <Table.Cell>
                    {m.attacks} / {m.attack_limit + m.bonus_attack_limit}
                  </Table.Cell>
                  <Table.Cell>
                    {m.attack_limit} + {m.bonus_attack_limit}
                  </Table.Cell>
                  <Table.Cell>{m.capital_resources_looted.toLocaleString()}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </TableScrollArea>
      )}
    </Box>
  );
}
