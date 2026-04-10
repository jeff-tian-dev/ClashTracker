import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Box,
  Heading,
  Card,
  Flex,
  Text,
  Badge,
  Grid,
  Dialog,
  Button,
  IconButton,
  Callout,
  Select,
  Tabs,
} from "@radix-ui/themes";
import { TrashIcon } from "@radix-ui/react-icons";
import { api, TrackedClan, War } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { DIALOG_CONTENT_SM } from "../lib/dialogClasses";
import { WarPlayersLeaderboard } from "../components/WarPlayersLeaderboard";

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
  const tab = searchParams.get("tab") === "players" ? "players" : "logs";
  const clanFromUrl = searchParams.get("clan")?.trim() || "";

  const { isAdmin, adminKey } = useAdmin();

  const [trackedClans, setTrackedClans] = useState<TrackedClan[]>([]);
  const [clansLoading, setClansLoading] = useState(true);

  const [wars, setWars] = useState<War[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .trackedClans()
      .then((res) => setTrackedClans(res.data))
      .catch(() => setTrackedClans([]))
      .finally(() => setClansLoading(false));
  }, []);

  useEffect(() => {
    if (clansLoading || trackedClans.length === 0) return;
    if (!searchParams.get("clan")) {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev);
          n.set("clan", trackedClans[0].clan_tag);
          return n;
        },
        { replace: true },
      );
    }
  }, [clansLoading, trackedClans, searchParams, setSearchParams]);

  useEffect(() => {
    if (clansLoading) return;
    if (trackedClans.length === 0) {
      setWars([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    if (!clanFromUrl) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .wars({
        page: String(page),
        page_size: "20",
        clan_tag: clanFromUrl,
      })
      .then((res) => {
        setWars(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        setWars([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [page, clanFromUrl, clansLoading, trackedClans.length]);

  async function handleDelete(id: number) {
    try {
      await api.deleteWar(id, adminKey);
      setWars((prev) => prev.filter((w) => w.id !== id));
      setTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to delete war", err);
    }
  }

  function setTab(next: string) {
    setSearchParams((prev) => {
      const n = new URLSearchParams(prev);
      n.set("tab", next);
      return n;
    });
  }

  function setClanTag(next: string) {
    setSearchParams((prev) => {
      const n = new URLSearchParams(prev);
      n.set("clan", next);
      n.set("page", "1");
      return n;
    });
  }

  if (clansLoading) {
    return <LoadingSpinner />;
  }

  if (trackedClans.length === 0) {
    return (
      <Box>
        <Heading size="6" mb="4">
          Clan Wars
        </Heading>
        <Callout.Root color="amber" role="status">
          <Callout.Text>
            Add a tracked clan to see wars and player stats for that clan.
          </Callout.Text>
        </Callout.Root>
      </Box>
    );
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Clan Wars
      </Heading>

      <Flex align="center" gap="3" wrap="wrap" mb="4">
        <Text size="2" weight="medium">
          Clan
        </Text>
        <Select.Root value={clanFromUrl || undefined} onValueChange={setClanTag}>
          <Select.Trigger placeholder="Select clan" />
          <Select.Content position="popper">
            {trackedClans.map((c) => (
              <Select.Item key={c.clan_tag} value={c.clan_tag}>
                {c.clans?.name ? `${c.clans.name} (${c.clan_tag})` : c.clan_tag}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>

      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List mb="4">
          <Tabs.Trigger value="logs">Logs</Tabs.Trigger>
          <Tabs.Trigger value="players">Players</Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="logs">
          {loading ? (
            <LoadingSpinner />
          ) : wars.length === 0 ? (
            <EmptyState message="No wars recorded for this clan yet." />
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
                            Destruction: {w.clan_destruction_pct.toFixed(1)}% -{" "}
                            {w.opponent_destruction_pct.toFixed(1)}%
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
                            Delete the war vs {w.opponent_name || "Unknown"} (
                            {new Date(w.start_time).toLocaleDateString()})? This also removes all
                            associated attacks.
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
                              <Button color="red" onClick={() => handleDelete(w.id)}>
                                Delete
                              </Button>
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
                onChange={(p) =>
                  setSearchParams((prev) => {
                    const n = new URLSearchParams(prev);
                    n.set("page", String(p));
                    return n;
                  })
                }
              />
            </>
          )}
        </Tabs.Content>

        <Tabs.Content value="players">
          <WarPlayersLeaderboard clanTag={clanFromUrl} />
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  );
}
