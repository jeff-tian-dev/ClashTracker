import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Box, Heading, Card, Flex, Text, Badge, Grid, Dialog, Button, IconButton } from "@radix-ui/themes";
import { TrashIcon } from "@radix-ui/react-icons";
import { api, Raid } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";

export function Raids() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") || "1");
  const { isAdmin, adminKey } = useAdmin();

  const [raids, setRaids] = useState<Raid[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  async function handleDelete(id: number) {
    try {
      await api.deleteRaid(id, adminKey);
      setRaids((prev) => prev.filter((r) => r.id !== id));
      setTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to delete raid", err);
    }
  }

  useEffect(() => {
    setLoading(true);
    api.raids({ page: String(page), page_size: "20" })
      .then((res) => {
        setRaids(res.data);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <Box>
      <Heading size="6" mb="4">
        Capital Raids
      </Heading>

      {loading ? (
        <LoadingSpinner />
      ) : raids.length === 0 ? (
        <EmptyState message="No raid seasons recorded yet." />
      ) : (
        <>
          <Grid columns={{ initial: "1", md: "2" }} gap="4">
            {raids.map((r) => (
              <Box key={r.id} className="relative">
                <Link to={`/raids/${r.id}`} className="no-underline">
                  <Card className="hover:shadow-md transition-shadow">
                    <Flex justify="between" align="start">
                      <Box>
                        <Text weight="bold" size="3">
                          {new Date(r.start_time).toLocaleDateString()} —{" "}
                          {new Date(r.end_time).toLocaleDateString()}
                        </Text>
                        <Text size="2" color="gray" as="p">
                          {r.total_attacks} attacks &middot; {r.raids_completed} raids
                        </Text>
                      </Box>
                      <Badge color={r.state === "ended" ? "gray" : "green"}>
                        {r.state === "ended" ? "Ended" : "Ongoing"}
                      </Badge>
                    </Flex>
                    <Flex gap="4" mt="3">
                      <Text size="2">
                        Loot: <Text weight="bold">{r.capital_total_loot.toLocaleString()}</Text>
                      </Text>
                      <Text size="2">
                        Districts: <Text weight="bold">{r.enemy_districts_destroyed}</Text>
                      </Text>
                    </Flex>
                  </Card>
                </Link>
                {isAdmin && (
                  <Dialog.Root>
                    <Dialog.Trigger>
                      <IconButton
                        variant="soft"
                        color="red"
                        size="1"
                        className="!absolute top-2 right-2 z-10"
                      >
                        <TrashIcon />
                      </IconButton>
                    </Dialog.Trigger>
                    <Dialog.Content maxWidth="400px">
                      <Dialog.Title>Delete Raid</Dialog.Title>
                      <Dialog.Description>
                        Delete the raid from {new Date(r.start_time).toLocaleDateString()} — {new Date(r.end_time).toLocaleDateString()}? This also removes all member participation data.
                      </Dialog.Description>
                      <Flex gap="3" mt="4" justify="end">
                        <Dialog.Close>
                          <Button variant="soft" color="gray">Cancel</Button>
                        </Dialog.Close>
                        <Dialog.Close>
                          <Button color="red" onClick={() => handleDelete(r.id)}>Delete</Button>
                        </Dialog.Close>
                      </Flex>
                    </Dialog.Content>
                  </Dialog.Root>
                )}
              </Box>
            ))}
          </Grid>
          <Pagination
            page={page}
            pageSize={20}
            total={total}
            onChange={(p) => setSearchParams({ page: String(p) })}
          />
        </>
      )}
    </Box>
  );
}
