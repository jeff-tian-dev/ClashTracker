import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Box, Heading, Table, TextField, Dialog, Flex, Button, IconButton, Badge, Text } from "@radix-ui/themes";
import { MagnifyingGlassIcon, TrashIcon } from "@radix-ui/react-icons";
import { api, Player } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { TableScrollArea } from "../components/TableScrollArea";
import { DIALOG_CONTENT_SM } from "../lib/dialogClasses";
import { formatLeftAgo } from "../lib/formatRelativeLeft";

export function Players() {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") || "1");
  const search = searchParams.get("search") || "";
  const { isAdmin, adminKey } = useAdmin();

  const [players, setPlayers] = useState<Player[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(search);

  async function handleDelete(tag: string) {
    try {
      await api.deletePlayer(tag, adminKey);
      setPlayers((prev) => prev.filter((p) => p.tag !== tag));
      setTotal((t) => t - 1);
    } catch (err) {
      console.error("Failed to delete player", err);
    }
  }

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page), page_size: "20" };
    if (search) params.search = search;

    api.players(params)
      .then((res) => {
        setPlayers(res.data);
        setTotal(res.total);
      })
      .finally(() => setLoading(false));
  }, [page, search]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchParams(searchInput ? { search: searchInput, page: "1" } : {});
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

      {loading ? (
        <LoadingSpinner />
      ) : players.length === 0 ? (
        <EmptyState message="No players found." />
      ) : (
        <>
          <TableScrollArea>
            <Table.Root variant="surface" className="min-w-[720px]">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>TH</Table.ColumnHeaderCell>
                  <Table.ColumnHeaderCell>Trophies</Table.ColumnHeaderCell>
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
                  <Table.Cell>{p.war_stars}</Table.Cell>
                  <Table.Cell>{p.role || "—"}</Table.Cell>
                  <Table.Cell>{p.league_name || "—"}</Table.Cell>
                  <Table.Cell>
                    <Flex gap="2" wrap="wrap" align="center">
                      {p.is_always_tracked && (
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
              const next: Record<string, string> = { page: String(p) };
              if (search) next.search = search;
              setSearchParams(next);
            }}
          />
        </>
      )}
    </Box>
  );
}
