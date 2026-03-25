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
import { PlusIcon, TrashIcon, Pencil1Icon } from "@radix-ui/react-icons";
import { api, TrackedPlayer } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";
import { TableScrollArea } from "../components/TableScrollArea";
import { DIALOG_CONTENT_SM } from "../lib/dialogClasses";

function displayLabel(r: TrackedPlayer) {
  const n = r.display_name?.trim();
  return n || "Unknown player";
}

export function TrackedPlayers() {
  const { isAdmin, adminKey } = useAdmin();
  const [rows, setRows] = useState<TrackedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTag, setNewTag] = useState("");
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editRow, setEditRow] = useState<TrackedPlayer | null>(null);
  const [editName, setEditName] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

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
    if (!newTag.trim() || !adminKey) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.addTrackedPlayer(newTag.trim(), newNote.trim() || undefined, adminKey);
      setNewTag("");
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

  function openEdit(r: TrackedPlayer) {
    setEditRow(r);
    setEditName(r.display_name?.trim() ? r.display_name.trim() : "");
    setEditError(null);
  }

  async function handleSaveEdit() {
    if (!editRow || !adminKey) return;
    const name = editName.trim();
    if (!name) {
      setEditError("Name is required");
      return;
    }
    setEditSaving(true);
    setEditError(null);
    try {
      await api.updateTrackedPlayerDisplayName(editRow.player_tag, name, adminKey);
      setEditRow(null);
      load();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setEditSaving(false);
    }
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        July Players
      </Heading>
      <Text size="2" color="gray" mb="4" style={{ display: "block", maxWidth: 640 }}>
        The display name is taken from your player database when you add a tag (or &quot;Unknown
        player&quot; if they are not ingested yet). You can fix names with the edit control on each
        row. Adding or removing tags requires admin.
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
                  Note (optional)
                </Text>
                <TextField.Root
                  placeholder="Scout account"
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                />
              </Box>
              <Button type="submit" disabled={submitting || !newTag.trim()}>
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
          Unlock admin in the sidebar to add or remove July roster players.
        </Text>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : rows.length === 0 ? (
        <EmptyState message="No July roster players yet. Admins can add a player tag above." />
      ) : (
        <TableScrollArea>
          <Table.Root variant="surface" className="min-w-[560px]">
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
                <Table.Cell>
                  <Flex align="center" gap="2" className="group/name min-w-0 max-w-[280px]">
                    <Text className="truncate">{displayLabel(r)}</Text>
                    {isAdmin && (
                      <IconButton
                        type="button"
                        variant="ghost"
                        color="gray"
                        size={{ initial: "2", md: "1" }}
                        className="shrink-0 opacity-100 transition-opacity md:opacity-0 md:group-hover/name:opacity-100"
                        aria-label="Edit name"
                        onClick={() => openEdit(r)}
                      >
                        <Pencil1Icon width={14} height={14} />
                      </IconButton>
                    )}
                  </Flex>
                </Table.Cell>
                <Table.Cell>{r.note || "—"}</Table.Cell>
                <Table.Cell>{new Date(r.added_at).toLocaleDateString()}</Table.Cell>
                {isAdmin && (
                  <Table.Cell>
                    <Dialog.Root>
                      <Dialog.Trigger>
                        <IconButton variant="ghost" color="red" size={{ initial: "2", md: "1" }}>
                          <TrashIcon />
                        </IconButton>
                      </Dialog.Trigger>
                      <Dialog.Content className={DIALOG_CONTENT_SM}>
                        <Dialog.Title>Remove from July roster</Dialog.Title>
                        <Dialog.Description>
                          {`Remove ${displayLabel(r)} (${r.player_tag}) from the July list? They will only update again if they are in a tracked clan.`}
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
        </TableScrollArea>
      )}

      <Dialog.Root open={editRow !== null} onOpenChange={(open) => !open && setEditRow(null)}>
        <Dialog.Content className={DIALOG_CONTENT_SM}>
          <Dialog.Title>Edit display name</Dialog.Title>
          <Dialog.Description size="2" color="gray" mb="3">
            {editRow?.player_tag}
          </Dialog.Description>
          <Box mb="3">
            <TextField.Root
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Player name"
            />
          </Box>
          {editError && (
            <Text size="2" color="red" mb="2">
              {editError}
            </Text>
          )}
          <Flex
            gap="3"
            justify="end"
            direction={{ initial: "column", sm: "row" }}
            wrap="wrap"
          >
            <Dialog.Close>
              <Button variant="soft" color="gray" disabled={editSaving}>
                Cancel
              </Button>
            </Dialog.Close>
            <Button onClick={handleSaveEdit} disabled={editSaving}>
              Save
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
