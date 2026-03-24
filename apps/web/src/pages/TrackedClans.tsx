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
import { api, TrackedClan } from "../lib/api";
import { useAdmin } from "../lib/AdminContext";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

export function TrackedClans() {
  const { isAdmin, adminKey } = useAdmin();
  const [clans, setClans] = useState<TrackedClan[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTag, setNewTag] = useState("");
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClans = useCallback(() => {
    setLoading(true);
    api.trackedClans()
      .then((res) => setClans(res.data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadClans();
  }, [loadClans]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTag.trim() || !adminKey) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.addTrackedClan(newTag.trim(), newNote.trim() || undefined, adminKey);
      setNewTag("");
      setNewNote("");
      loadClans();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add clan");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(tag: string) {
    if (!adminKey) return;
    try {
      await api.removeTrackedClan(tag, adminKey);
      loadClans();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove clan");
    }
  }

  return (
    <Box>
      <Heading size="6" mb="4">
        Tracked Clans
      </Heading>
      <Text size="2" color="gray" mb="4" style={{ display: "block", maxWidth: 640 }}>
        Tracked clans drive ingestion. Adding or removing a tag requires admin.
      </Text>

      {isAdmin ? (
        <Card mb="5">
          <form onSubmit={handleAdd}>
            <Flex gap="3" align="end" wrap="wrap">
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Clan Tag
                </Text>
                <TextField.Root
                  placeholder="#ABC123"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                />
              </Box>
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Note (optional)
                </Text>
                <TextField.Root
                  placeholder="My main clan"
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                />
              </Box>
              <Button type="submit" disabled={submitting || !newTag.trim()}>
                <PlusIcon /> Add Clan
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
          Unlock admin in the sidebar to add or remove tracked clans.
        </Text>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : clans.length === 0 ? (
        <EmptyState message="No clans being tracked. Admins can add a clan tag above." />
      ) : (
        <Table.Root variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell>Tag</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Clan Name</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Level</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Members</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Note</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Added</Table.ColumnHeaderCell>
              {isAdmin && <Table.ColumnHeaderCell />}
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {clans.map((c) => (
              <Table.Row key={c.clan_tag}>
                <Table.Cell>
                  <Text weight="medium">{c.clan_tag}</Text>
                </Table.Cell>
                <Table.Cell>{c.clans?.name || "—"}</Table.Cell>
                <Table.Cell>{c.clans?.clan_level ?? "—"}</Table.Cell>
                <Table.Cell>{c.clans?.members_count ?? "—"}</Table.Cell>
                <Table.Cell>{c.note || "—"}</Table.Cell>
                <Table.Cell>
                  {new Date(c.added_at).toLocaleDateString()}
                </Table.Cell>
                {isAdmin && (
                  <Table.Cell>
                    <Dialog.Root>
                      <Dialog.Trigger>
                        <IconButton variant="ghost" color="red" size="1">
                          <TrashIcon />
                        </IconButton>
                      </Dialog.Trigger>
                      <Dialog.Content maxWidth="400px">
                        <Dialog.Title>Remove Clan</Dialog.Title>
                        <Dialog.Description>
                          Stop tracking {c.clans?.name || c.clan_tag}? This won't delete existing data.
                        </Dialog.Description>
                        <Flex gap="3" mt="4" justify="end">
                          <Dialog.Close>
                            <Button variant="soft" color="gray">Cancel</Button>
                          </Dialog.Close>
                          <Dialog.Close>
                            <Button color="red" onClick={() => handleRemove(c.clan_tag)}>
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
