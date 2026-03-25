import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Box, Heading, Card, Flex, Text, Badge, Grid, Dialog, Button, IconButton } from "@radix-ui/themes";
import { TrashIcon } from "@radix-ui/react-icons";
import { api, War } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { DIALOG_CONTENT_SM } from "../lib/dialogClasses";

function resultBadge(result: string | null, state: string) {
  if (state === "preparation") return <Badge color="blue">Prep</Badge>;
  if (state === "inWar") return <Badge color="orange">In War</Badge>;
  if (!result) return <Badge color="gray">Unknown</Badge>;
  if (result === "win") return <Badge color="green">Win</Badge>;
  if (result === "lose") return <Badge color="red">Loss</Badge>;
  return <Badge color="yellow">Tie</Badge>;
}

export function Wars() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") || "1");
  const { isAdmin, adminKey } = useAdmin();

  const [wars, setWars] = useState<War[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  async function handleDelete(id: number) {
    try {
      await api.deleteWar(id, adminKey);
      setWars((prev) => prev.filter((w) => w.id !== id));
      setTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to delete war", err);
    }
  }

  useEffect(() => {
    setLoading(true);
    api.wars({ page: String(page), page_size: "20" })
      .then((res) => {
        setWars(res.data);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <Box>
      <Heading size="6" mb="4">
        Clan Wars
      </Heading>

      {loading ? (
        <LoadingSpinner />
      ) : wars.length === 0 ? (
        <EmptyState message="No wars recorded yet." />
      ) : (
        <>
          <Grid columns={{ initial: "1", md: "2" }} gap="4">
            {wars.map((w) => (
              <Box key={w.id} className="relative">
                <Link to={`/wars/${w.id}`} className="no-underline">
                  <Card className="hover:shadow-md transition-shadow">
                    <Flex justify="between" align="start">
                      <Box>
                        <Text weight="bold" size="3">
                          vs {w.opponent_name || "Unknown"}
                        </Text>
                        <Text size="2" color="gray" as="p">
                          {w.team_size}v{w.team_size} &middot;{" "}
                          {new Date(w.start_time).toLocaleDateString()}
                        </Text>
                      </Box>
                      {resultBadge(w.result, w.state)}
                    </Flex>
                    <Flex gap="4" mt="3">
                      <Text size="2">
                        Stars: <Text weight="bold">{w.clan_stars}</Text> -{" "}
                        <Text weight="bold">{w.opponent_stars}</Text>
                      </Text>
                      <Text size="2">
                        Destruction: {w.clan_destruction_pct.toFixed(1)}% - {w.opponent_destruction_pct.toFixed(1)}%
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
                        size={{ initial: "2", md: "1" }}
                        className="!absolute top-2 right-2 z-10 touch-manipulation"
                      >
                        <TrashIcon />
                      </IconButton>
                    </Dialog.Trigger>
                    <Dialog.Content className={DIALOG_CONTENT_SM}>
                      <Dialog.Title>Delete War</Dialog.Title>
                      <Dialog.Description>
                        Delete the war vs {w.opponent_name || "Unknown"} ({new Date(w.start_time).toLocaleDateString()})? This also removes all associated attacks.
                      </Dialog.Description>
                      <Flex
                        gap="3"
                        mt="4"
                        justify="end"
                        direction={{ initial: "column", sm: "row" }}
                        wrap="wrap"
                      >
                        <Dialog.Close>
                          <Button variant="soft" color="gray">Cancel</Button>
                        </Dialog.Close>
                        <Dialog.Close>
                          <Button color="red" onClick={() => handleDelete(w.id)}>Delete</Button>
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
