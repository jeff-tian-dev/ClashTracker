import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Box, Card, Flex, Heading, Text, Badge, Table } from "@radix-ui/themes";
import { ArrowLeftIcon, StarFilledIcon } from "@radix-ui/react-icons";
import { api, WarDetail as WarDetailType } from "../lib/api";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";

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

export function WarDetail() {
  const { id } = useParams<{ id: string }>();
  const [war, setWar] = useState<WarDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.war(Number(id))
      .then(setWar)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (error) return <EmptyState message={error} />;
  if (!war) return <EmptyState message="War not found." />;

  return (
    <Box>
      <Link to="/wars" className="inline-flex items-center gap-1 text-sm text-[var(--accent-11)] hover:underline mb-4">
        <ArrowLeftIcon /> Back to Wars
      </Link>
      <Flex align="center" gap="3" mb="4">
        <Heading size="6">vs {war.opponent_name || "Unknown"}</Heading>
        <Badge color={war.result === "win" ? "green" : war.result === "lose" ? "red" : "gray"}>
          {war.result?.toUpperCase() || war.state}
        </Badge>
      </Flex>

      <Card mb="5">
        <Flex gap="6" wrap="wrap" p="2">
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Team Size</Text>
            <Text weight="bold">{war.team_size}v{war.team_size}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Our Stars</Text>
            <Text weight="bold">{war.clan_stars}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Their Stars</Text>
            <Text weight="bold">{war.opponent_stars}</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Our Destruction</Text>
            <Text weight="bold">{war.clan_destruction_pct.toFixed(1)}%</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">Their Destruction</Text>
            <Text weight="bold">{war.opponent_destruction_pct.toFixed(1)}%</Text>
          </Flex>
          <Flex direction="column" gap="1">
            <Text size="1" color="gray">War Date</Text>
            <Text weight="bold">{new Date(war.start_time).toLocaleDateString()}</Text>
          </Flex>
        </Flex>
      </Card>

      <Heading size="4" mb="3">
        Attacks ({war.attacks.length})
      </Heading>

      {war.attacks.length === 0 ? (
        <EmptyState message="No attacks recorded." />
      ) : (
        <TableScrollArea>
          <Table.Root variant="surface" className="min-w-[640px]">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeaderCell>#</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Attacker</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Defender</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Stars</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Destruction</Table.ColumnHeaderCell>
                <Table.ColumnHeaderCell>Duration</Table.ColumnHeaderCell>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {war.attacks.map((a) => (
                <Table.Row key={a.id}>
                  <Table.Cell>{a.attack_order}</Table.Cell>
                  <Table.Cell>{a.attacker_tag}</Table.Cell>
                  <Table.Cell>{a.defender_tag}</Table.Cell>
                  <Table.Cell>
                    <Stars count={a.stars} />
                  </Table.Cell>
                  <Table.Cell>{a.destruction_percentage.toFixed(1)}%</Table.Cell>
                  <Table.Cell>{a.duration ? `${a.duration}s` : "—"}</Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </TableScrollArea>
      )}
    </Box>
  );
}
