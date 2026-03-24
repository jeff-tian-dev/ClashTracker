import { useEffect, useState, useCallback } from "react";
import {
  Box,
  Heading,
  Card,
  Flex,
  Text,
  TextField,
  Button,
  Table,
  Dialog,
  IconButton,
} from "@radix-ui/themes";
import { PlusIcon, TrashIcon } from "@radix-ui/react-icons";
import { api, TrackedPlayer } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

export function TrackedPlayers() {
  const { isAdmin, adminKey } = useAdmin();
  const [rows, setRows] = useState<TrackedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTag, setNewTag] = useState("");
  const [newName, setNewName] = useState("");
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .trackedPlayers()
      .then((res) => setRows(res.data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTag.trim() || !newName.trim() || !adminKey) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.addTrackedPlayer(
        newTag.trim(),
        newName.trim(),
        newNote.trim() || undefined,
        adminKey,
      );
      setNewTag("");
      setNewName("");
      setNewNote("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add player");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(tag: string) {
    if (!adminKey) return;
    try {
      await api.removeTrackedPlayer(tag, adminKey);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove");
    }
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Tracked Players
      </Heading>
      <Text size="2" color="gray" mb="4" style={{ display: "block", maxWidth: 640 }}>
        Always-tracked players are refreshed every ingest run even if they are not in a tracked clan.
        Adding or removing requires admin.
      </Text>

      {isAdmin ? (
        <Card mb="5">
          <form onSubmit={handleAdd}>
            <Flex gap="3" align="end" wrap="wrap">
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Player Tag
                </Text>
                <TextField.Root
                  placeholder="#ABC0ABC"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                />
              </Box>
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Name
                </Text>
                <TextField.Root
                  placeholder="In-game name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </Box>
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Note (optional)
                </Text>
                <TextField.Root
                  placeholder="Scout account"
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                />
              </Box>
              <Button type="submit" disabled={submitting || !newTag.trim() || !newName.trim()}>
                <PlusIcon /> Add
              </Button>
            </Flex>
            {error && (
              <Text size="2" color="red" mt="2">
                {error}
              </Text>
            )}
          </form>
        </Card>
      ) : (
        <Text size="2" color="gray" mb="4">
          Unlock admin in the sidebar to add or remove always-tracked players.
        </Text>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : rows.length === 0 ? (
        <EmptyState message="No always-tracked players. Admins can add tag and name above." />
      ) : (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Tag</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Note</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Added</Table.ColumnHeaderCell>
              {isAdmin && <Table.ColumnHeaderCell />}
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {rows.map((r) => (
              <Table.Row key={r.player_tag}>
                <Table.Cell>
                  <Text weight="medium">{r.player_tag}</Text>
                </Table.Cell>
                <Table.Cell>{r.name?.trim() ? r.name : "—"}</Table.Cell>
                <Table.Cell>{r.note || "—"}</Table.Cell>
                <Table.Cell>{new Date(r.added_at).toLocaleDateString()}</Table.Cell>
                {isAdmin && (
                  <Table.Cell>
                    <Dialog.Root>
                      <Dialog.Trigger>
                        <IconButton variant="ghost" color="red" size="1">
                          <TrashIcon />
                        </IconButton>
                      </Dialog.Trigger>
                      <Dialog.Content maxWidth="400px">
                        <Dialog.Title>Remove always-track</Dialog.Title>
                        <Dialog.Description>
                          Stop always-tracking {r.name?.trim() || r.player_tag} ({r.player_tag})? They will
                          only update again if in a tracked clan.
                        </Dialog.Description>
                        <Flex gap="3" mt="4" justify="end">
                          <Dialog.Close>
                            <Button variant="soft" color="gray">
                              Cancel
                            </Button>
                          </Dialog.Close>
                          <Dialog.Close>
                            <Button color="red" onClick={() => handleRemove(r.player_tag)}>
                              Remove
                            </Button>
                          </Dialog.Close>
                        </Flex>
                      </Dialog.Content>
                    </Dialog.Root>
                  </Table.Cell>
                )}
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}
    </Box>
  );
}
