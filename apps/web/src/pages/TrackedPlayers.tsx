import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
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

export type TrackedPlayerGroup = "clan_july" | "external";

function displayLabel(r: TrackedPlayer) {
  const n = r.display_name?.trim();
  return n || "Unknown player";
}

type SectionProps = {
  title: string;
  description: string;
  adminLockedHint: string;
  emptyMessage: string;
  removeTitle: string;
  removeDescription: (r: TrackedPlayer) => string;
  trackingGroup: TrackedPlayerGroup;
  rows: TrackedPlayer[];
  isAdmin: boolean;
  adminKey: string | null;
  onReload: () => void;
  onEdit: (r: TrackedPlayer) => void;
  sectionError: string | null;
  setSectionError: (msg: string | null) => void;
};

function TrackedPlayerTableSection({
  title,
  description,
  adminLockedHint,
  emptyMessage,
  removeTitle,
  removeDescription,
  trackingGroup,
  rows,
  isAdmin,
  adminKey,
  onReload,
  onEdit,
  sectionError,
  setSectionError,
}: SectionProps) {
  const [newTag, setNewTag] = useState("");
  const [newName, setNewName] = useState("");
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTag.trim() || !adminKey) return;
    setSubmitting(true);
    setSectionError(null);
    try {
      await api.addTrackedPlayer(newTag.trim(), adminKey, {
        note: newNote.trim() || undefined,
        display_name: newName.trim() || undefined,
        tracking_group: trackingGroup,
      });
      setNewTag("");
      setNewName("");
      setNewNote("");
      onReload();
    } catch (err) {
      setSectionError(err instanceof Error ? err.message : "Failed to add player");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(tag: string) {
    if (!adminKey) return;
    try {
      await api.removeTrackedPlayer(tag, adminKey);
      onReload();
    } catch (err) {
      setSectionError(err instanceof Error ? err.message : "Failed to remove");
    }
  }

  return (
    <Box mb="6">
      <Heading size="5" mb="2">
        {title}
      </Heading>
      <Text size="2" color="gray" mb="3" style={{ display: "block", maxWidth: 640 }}>
        {description}
      </Text>

      {isAdmin ? (
        <Card mb="4">
          <form onSubmit={handleAdd}>
            <Flex gap="3" align="end" wrap="wrap">
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Player tag
                </Text>
                <TextField.Root
                  placeholder="#ABC0ABC"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                />
              </Box>
              <Box style={{ flex: 1, minWidth: 200 }}>
                <Text as="label" size="2" weight="medium" mb="1">
                  Name (optional)
                </Text>
                <TextField.Root
                  placeholder="Override display name"
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
              <Button type="submit" disabled={submitting || !newTag.trim()}>
                <PlusIcon /> Add
              </Button>
            </Flex>
            {sectionError && (
              <Text size="2" color="red" mt="2">
                {sectionError}
              </Text>
            )}
          </form>
        </Card>
      ) : (
        <Text size="2" color="gray" mb="3">
          {adminLockedHint}
        </Text>
      )}

      {rows.length === 0 ? (
        <EmptyState message={emptyMessage} />
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
                    <Text weight="medium" asChild>
                      <Link
                        to={`/players/${encodeURIComponent(r.player_tag)}`}
                        className="text-[var(--accent-11)] hover:underline"
                      >
                        {r.player_tag}
                      </Link>
                    </Text>
                  </Table.Cell>
                  <Table.Cell>
                    <Flex align="center" gap="2" className="group/name min-w-0 max-w-[280px]">
                      <Text className="truncate" asChild>
                        <Link
                          to={`/players/${encodeURIComponent(r.player_tag)}`}
                          className="text-[var(--accent-11)] hover:underline truncate"
                        >
                          {displayLabel(r)}
                        </Link>
                      </Text>
                      {isAdmin && (
                        <IconButton
                          type="button"
                          variant="ghost"
                          color="gray"
                          size={{ initial: "2", md: "1" }}
                          className="shrink-0 opacity-100 transition-opacity md:opacity-0 md:group-hover/name:opacity-100"
                          aria-label="Edit name"
                          onClick={() => onEdit(r)}
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
                          <Dialog.Title>{removeTitle}</Dialog.Title>
                          <Dialog.Description>{removeDescription(r)}</Dialog.Description>
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
    </Box>
  );
}

export function TrackedPlayers() {
  const { isAdmin, adminKey } = useAdmin();
  const [clanRows, setClanRows] = useState<TrackedPlayer[]>([]);
  const [externalRows, setExternalRows] = useState<TrackedPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [clanSectionError, setClanSectionError] = useState<string | null>(null);
  const [externalSectionError, setExternalSectionError] = useState<string | null>(null);

  const [editRow, setEditRow] = useState<TrackedPlayer | null>(null);
  const [editName, setEditName] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.trackedPlayers({ tracking_group: "clan_july" }),
      api.trackedPlayers({ tracking_group: "external" }),
    ])
      .then(([clan, ext]) => {
        setClanRows(clan.data);
        setExternalRows(ext.data);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
        Tracked Players
      </Heading>
      <Text size="2" color="gray" mb="5" style={{ display: "block", maxWidth: 720 }}>
        Clan list is your July roster. External list is for players you track who are not on that
        clan list. Names default from your player database when you add a tag (or &quot;Unknown
        player&quot; until ingested); you can override on add or edit later. Adding or removing
        requires admin.
      </Text>

      {loading ? (
        <LoadingSpinner />
      ) : (
        <>
      <TrackedPlayerTableSection
        title="Clan players (July)"
        description="Pinned members of your July clan roster for ingestion and Legends."
        adminLockedHint="Unlock admin in the sidebar to add or remove clan roster players."
        emptyMessage="No clan roster players yet. Admins can add a player tag above."
        removeTitle="Remove from clan list"
        removeDescription={(r) =>
          `Remove ${displayLabel(r)} (${r.player_tag}) from the clan (July) list? They will only update again if they are in a tracked clan.`
        }
        trackingGroup="clan_july"
        rows={clanRows}
        isAdmin={isAdmin}
        adminKey={adminKey}
        onReload={load}
        onEdit={openEdit}
        sectionError={clanSectionError}
        setSectionError={setClanSectionError}
      />

      <TrackedPlayerTableSection
        title="External tracked players"
        description="Players outside the July clan list you still want to ingest and follow (Legends, stats, activity)."
        adminLockedHint="Unlock admin in the sidebar to add or remove external tracked players."
        emptyMessage="No external tracked players yet. Admins can add a player tag above."
        removeTitle="Remove from external list"
        removeDescription={(r) =>
          `Remove ${displayLabel(r)} (${r.player_tag}) from the external tracked list?`
        }
        trackingGroup="external"
        rows={externalRows}
        isAdmin={isAdmin}
        adminKey={adminKey}
        onReload={load}
        onEdit={openEdit}
        sectionError={externalSectionError}
        setSectionError={setExternalSectionError}
      />
        </>
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
          <Flex gap="3" justify="end" direction={{ initial: "column", sm: "row" }} wrap="wrap">
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
