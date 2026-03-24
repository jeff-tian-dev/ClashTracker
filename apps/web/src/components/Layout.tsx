import { useState } from "react";
import { Link, useLocation, Outlet } from "react-router-dom";
import { Box, Flex, Text, TextField, Button, Badge, IconButton } from "@radix-ui/themes";
import {
  DashboardIcon,
  PersonIcon,
  CrossCircledIcon,
  RocketIcon,
  GearIcon,
  BookmarkIcon,
  LockClosedIcon,
  LockOpen1Icon,
  StarFilledIcon,
  MoonIcon,
  SunIcon,
} from "@radix-ui/react-icons";
import { useAdmin } from "../lib/AdminContext";
import { useThemePreference } from "../lib/ThemePreferenceContext";
import { api } from "../lib/api";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: DashboardIcon },
  { to: "/players", label: "Players", icon: PersonIcon },
  { to: "/wars", label: "Wars", icon: CrossCircledIcon },
  { to: "/raids", label: "Capital Raids", icon: RocketIcon },
  { to: "/legends", label: "Legends", icon: StarFilledIcon },
  { to: "/tracked-clans", label: "Tracked Clans", icon: GearIcon },
  { to: "/july-players", label: "July Players", icon: BookmarkIcon },
];

function ThemeToggle() {
  const { appearance, toggleAppearance } = useThemePreference();
  const isDark = appearance === "dark";
  return (
    <IconButton
      variant="ghost"
      color="gray"
      size="1"
      onClick={toggleAppearance}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? <SunIcon width={16} height={16} /> : <MoonIcon width={16} height={16} />}
    </IconButton>
  );
}

function AdminToggle() {
  const { isAdmin, setAdminKey, clearAdmin } = useAdmin();
  const [open, setOpen] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [error, setError] = useState("");
  const [verifying, setVerifying] = useState(false);

  async function handleUnlock() {
    if (!keyInput.trim()) return;
    setVerifying(true);
    setError("");
    try {
      await api.verifyAdmin(keyInput.trim());
      setAdminKey(keyInput.trim());
      setKeyInput("");
      setOpen(false);
    } catch {
      setError("Invalid key");
    } finally {
      setVerifying(false);
    }
  }

  if (isAdmin) {
    return (
      <Flex align="center" gap="2" px="3" py="2">
        <Badge color="red" size="1">Admin</Badge>
        <IconButton
          variant="ghost"
          color="gray"
          size="1"
          onClick={() => { clearAdmin(); setOpen(false); }}
          title="Lock admin"
        >
          <LockOpen1Icon />
        </IconButton>
      </Flex>
    );
  }

  if (!open) {
    return (
      <Box px="3" py="2">
        <IconButton
          variant="ghost"
          color="gray"
          size="1"
          onClick={() => setOpen(true)}
          title="Unlock admin"
        >
          <LockClosedIcon />
        </IconButton>
      </Box>
    );
  }

  return (
    <Flex direction="column" gap="2" px="3" py="2">
      <TextField.Root
        size="1"
        type="password"
        placeholder="Admin key"
        value={keyInput}
        onChange={(e) => setKeyInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleUnlock()}
      />
      <Flex gap="2">
        <Button size="1" disabled={verifying || !keyInput.trim()} onClick={handleUnlock}>
          Unlock
        </Button>
        <Button size="1" variant="soft" color="gray" onClick={() => { setOpen(false); setError(""); }}>
          Cancel
        </Button>
      </Flex>
      {error && <Text size="1" color="red">{error}</Text>}
    </Flex>
  );
}

export function Layout() {
  const location = useLocation();

  return (
    <Flex className="min-h-screen">
      <Box
        asChild
        className="w-60 shrink-0 border-r border-[var(--gray-5)] bg-[var(--gray-2)]"
      >
        <nav className="flex flex-col h-screen">
          <Box px="4" py="5">
            <Text size="5" weight="bold">
              Clash Tracker
            </Text>
          </Box>
          <Flex direction="column" gap="1" px="2" className="flex-1">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
              const active =
                to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm no-underline transition-colors ${
                    active
                      ? "bg-[var(--accent-3)] text-[var(--accent-11)] font-medium"
                      : "text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
                  }`}
                >
                  <Icon width={16} height={16} />
                  {label}
                </Link>
              );
            })}
          </Flex>
          <Box className="border-t border-[var(--gray-5)]" py="2" px="1">
            <Flex align="center" justify="between" gap="2" wrap="wrap" px="2">
              <ThemeToggle />
              <AdminToggle />
            </Flex>
          </Box>
        </nav>
      </Box>
      <Box className="flex-1 overflow-auto" p="6">
        <Outlet />
      </Box>
    </Flex>
  );
}
