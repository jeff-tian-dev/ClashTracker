import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Box, Heading, Table, TextField, Dialog, Flex, Button, IconButton, Badge, Text } from "@radix-ui/themes";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  BookmarkIcon,
  MagnifyingGlassIcon,
  TrashIcon,
} from "@radix-ui/react-icons";
import { api, Player } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { TableScrollArea } from "../components/TableScrollArea";
import { DIALOG_CONTENT_SM } from "../lib/dialogClasses";
import { formatLeftAgo } from "../lib/formatRelativeLeft";
import { ShieldIcon } from "../components/ShieldIcon";

type SortableColumn = "name" | "trophies" | "attacks_7d";

function activeSortFromParams(searchParams: URLSearchParams): SortableColumn | null {
  const s = searchParams.get("sort") || "";
  if (s === "name" || s === "trophies" || s === "attacks_7d") return s;
  return null;
}

export function Players() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") || "1");
  const search = searchParams.get("search") || "";
  const sortColumn = activeSortFromParams(searchParams);
  const sortOrder: "asc" | "desc" = searchParams.get("order") === "desc" ? "desc" : "asc";
  const { isAdmin, adminKey } = useAdmin();

  const [players, setPlayers] = useState<Player[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(search);
  const [pendingTrackTag, setPendingTrackTag] = useState<string | null>(null);

  async function handleDelete(tag: string) {
    try {
      await api.deletePlayer(tag, adminKey);
      setPlayers((prev) => prev.filter((p) => p.tag !== tag));
      setTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to delete player", err);
    }
  }

  function effectiveTrackedGroup(p: Player): "clan_july" | "external" | null {
    if (!p.is_always_tracked) return null;
    return p.tracking_group ?? "clan_july";
  }

  async function handleTrackedGroupAction(p: Player, target: "clan_july" | "external") {
    if (!adminKey) return;
    const current = effectiveTrackedGroup(p);
    if (current === target) return;

    setPendingTrackTag(p.tag);
    try {
      if (current == null) {
        await api.addTrackedPlayer(p.tag, adminKey, {
          tracking_group: target,
          display_name: p.name,
        });
      } else {
        await api.patchTrackedPlayer(p.tag, adminKey, { tracking_group: target });
      }
      setPlayers((prev) =>
        prev.map((row) =>
          row.tag === p.tag ? { ...row, is_always_tracked: true, tracking_group: target } : row,
        ),
      );
    } catch (err) {
      console.error("Failed to update tracked player", err);
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409")) {
        window.alert(
          "Could not add this player (already on a tracked list). Try again or refresh the page.",
        );
      } else {
        window.alert("Failed to update tracked list for this player.");
      }
    } finally {
      setPendingTrackTag(null);
    }
  }

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page), page_size: "20" };
    if (search) params.search = search;
    if (sortColumn) {
      params.sort = sortColumn;
      if (sortOrder === "desc") params.order = "desc";
    }

    api.players(params)
      .then((res) => {
        setPlayers(res.data);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [page, search, sortColumn, sortOrder]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const next = new URLSearchParams(searchParams);
    if (searchInput) next.set("search", searchInput);
    else next.delete("search");
    next.set("page", "1");
    setSearchParams(next);
  }

  function handleSortClick(field: SortableColumn) {
    const next = new URLSearchParams(searchParams);
    if (sortColumn === field) {
      next.set("order", sortOrder === "asc" ? "desc" : "asc");
    } else {
      next.set("sort", field);
      next.set("order", "asc");
    }
    next.set("page", "1");
    setSearchParams(next);
  }

  function resetRosterSort() {
    const next = new URLSearchParams(searchParams);
    next.delete("sort");
    next.delete("order");
    next.set("page", "1");
    setSearchParams(next);
  }

  function sortHeaderButton(field: SortableColumn, label: string) {
    const active = sortColumn === field;
    return (
      <button
        type="button"
        className="inline-flex items-center gap-1 font-inherit cursor-pointer border-0 bg-transparent p-0 text-left hover:text-[var(--accent-11)]"
        onClick={() => handleSortClick(field)}
      >
        {label}
        {active ? (sortOrder === "asc" ? <ArrowUpIcon /> : <ArrowDownIcon />) : null}
      </button>
    );
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Players
      </Heading>

      <form onSubmit={handleSearch} className="mb-4 max-w-sm">
        <TextField.Root
          placeholder="Search by name..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        >
          <TextField.Slot>
            <MagnifyingGlassIcon />
          </TextField.Slot>
        </TextField.Root>
      </form>

      {sortColumn != null && (
        <Text size="2" color="gray" mb="3" as="div">
          <button
            type="button"
            className="cursor-pointer border-0 bg-transparent p-0 underline text-inherit hover:text-[var(--accent-11)]"
            onClick={resetRosterSort}
          >
            Default roster order
          </button>
        </Text>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : players.length === 0 ? (
        <EmptyState message="No players found." />
      ) : (
        <>
          <TableScrollArea>
            <Table.Root variant="surface" className="min-w-[820px]">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeaderCell>{sortHeaderButton("name", "Name")}</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>TH</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>
                    {sortHeaderButton("trophies", "Trophies")}
                  </Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>
                    {sortHeaderButton("attacks_7d", "Attacks (7d)")}
                  </Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>War Stars</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>Role</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>League</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>Status</Table.ColumnHeaderCell>
                  {isAdmin && <Table.ColumnHeaderCell />}
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {players.map((p) => {
                  const leftAt = p.left_tracked_roster_at;
                  const isLeft = Boolean(leftAt);
                  const trackedG = effectiveTrackedGroup(p);
                  const shieldDisabled =
                    pendingTrackTag === p.tag || (p.is_always_tracked && trackedG === "clan_july");
                  const bookmarkDisabled =
                    pendingTrackTag === p.tag || (p.is_always_tracked && trackedG === "external");
                  return (
                <Table.Row key={p.tag} className={isLeft ? "opacity-60" : undefined}>
                  <Table.Cell>
                    <Flex direction="column" gap="1" align="start">
                      <Link
                        to={`/players/${encodeURIComponent(p.tag)}`}
                        className={
                          isLeft
                            ? "text-[var(--gray-11)] hover:underline font-medium"
                            : "text-[var(--accent-11)] hover:underline font-medium"
                        }
                      >
                        {p.name}
                      </Link>
                    </Flex>
                  </Table.Cell>
                  <Table.Cell>{p.town_hall_level}</Table.Cell>
                  <Table.Cell>{p.trophies.toLocaleString()}</Table.Cell>
                  <Table.Cell>{p.attacks_7d}</Table.Cell>
                  <Table.Cell>{p.war_stars}</Table.Cell>
                  <Table.Cell>{p.role || "—"}</Table.Cell>
                  <Table.Cell>{p.league_name || "—"}</Table.Cell>
                  <Table.Cell>
                    <Flex gap="2" wrap="wrap" align="center">
                      {p.is_always_tracked && p.tracking_group === "external" && (
                        <Badge size="1" color="amber" variant="soft">
                          External
                        </Badge>
                      )}
                      {p.is_always_tracked && p.tracking_group !== "external" && (
                        <Badge size="1" color="blue" variant="soft">
                          July
                        </Badge>
                      )}
                      {leftAt && (
                        <Badge size="1" color="gray" variant="surface">
                          {formatLeftAgo(leftAt)}
                        </Badge>
                      )}
                      {!leftAt && !p.is_always_tracked && (
                        <Text size="2" color="gray">—</Text>
                      )}
                    </Flex>
                  </Table.Cell>
                  {isAdmin && (
                    <Table.Cell>
                      <Flex gap="1" align="center" wrap="nowrap">
                        <IconButton
                          type="button"
                          variant="ghost"
                          color="gray"
                          size={{ initial: "2", md: "1" }}
                          disabled={shieldDisabled}
                          aria-label="Move player to Clan (July) tracked list"
                          title="Move player to Clan (July) tracked list"
                          onClick={() => handleTrackedGroupAction(p, "clan_july")}
                        >
                          <ShieldIcon />
                        </IconButton>
                        <IconButton
                          type="button"
                          variant="ghost"
                          color="gray"
                          size={{ initial: "2", md: "1" }}
                          disabled={bookmarkDisabled}
                          aria-label="Move player to external tracked list"
                          title="Move player to external tracked list"
                          onClick={() => handleTrackedGroupAction(p, "external")}
                        >
                          <BookmarkIcon />
                        </IconButton>
                        <Dialog.Root>
                          <Dialog.Trigger>
                            <IconButton variant="ghost" color="red" size={{ initial: "2", md: "1" }}>
                              <TrashIcon />
                            </IconButton>
                          </Dialog.Trigger>
                          <Dialog.Content className={DIALOG_CONTENT_SM}>
                            <Dialog.Title>Delete Player</Dialog.Title>
                            <Dialog.Description>
                              Remove {p.name} ({p.tag}) from the dashboard? This deletes their data from the database.
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
                                <Button color="red" onClick={() => handleDelete(p.tag)}>Delete</Button>
                              </Dialog.Close>
                            </Flex>
                          </Dialog.Content>
                        </Dialog.Root>
                      </Flex>
                    </Table.Cell>
                  )}
                </Table.Row>
                  );
                })}
              </Table.Body>
            </Table.Root>
          </TableScrollArea>
          <Pagination
            page={page}
            pageSize={20}
            total={total}
            onChange={(p) => {
              const next = new URLSearchParams(searchParams);
              next.set("page", String(p));
              setSearchParams(next);
            }}
          />
        </>
      )}
    </Box>
  );
}
