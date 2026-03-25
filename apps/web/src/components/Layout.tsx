import { useEffect, useState } from "react";
import { Link, useLocation, Outlet } from "react-router-dom";
import {
  Box,
  Flex,
  Text,
  TextField,
  Button,
  Badge,
  IconButton,
  Dialog,
} from "@radix-ui/themes";
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
  HamburgerMenuIcon,
  Cross2Icon,
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

const iconBtnSize = { initial: "2" as const, md: "1" as const };
const fieldBtnSize = { initial: "2" as const, md: "1" as const };

function ThemeToggle() {
  const { appearance, toggleAppearance } = useThemePreference();
  const isDark = appearance === "dark";
  return (
    <IconButton
      variant="ghost"
      color="gray"
      size={iconBtnSize}
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
        <Badge color="red" size={{ initial: "2", md: "1" }}>
          Admin
        </Badge>
        <IconButton
          variant="ghost"
          color="gray"
          size={iconBtnSize}
          onClick={() => {
            clearAdmin();
            setOpen(false);
          }}
          title="Lock admin"
          aria-label="Lock admin"
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
          size={iconBtnSize}
          onClick={() => setOpen(true)}
          title="Unlock admin"
          aria-label="Unlock admin"
        >
          <LockClosedIcon />
        </IconButton>
      </Box>
    );
  }

  return (
    <Flex direction="column" gap="2" px="3" py="2">
      <TextField.Root
        size={fieldBtnSize}
        type="password"
        placeholder="Admin key"
        value={keyInput}
        onChange={(e) => setKeyInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleUnlock()}
      />
      <Flex gap="2" direction={{ initial: "column", sm: "row" }} wrap="wrap">
        <Button
          size={fieldBtnSize}
          disabled={verifying || !keyInput.trim()}
          onClick={handleUnlock}
        >
          Unlock
        </Button>
        <Button
          size={fieldBtnSize}
          variant="soft"
          color="gray"
          onClick={() => {
            setOpen(false);
            setError("");
          }}
        >
          Cancel
        </Button>
      </Flex>
      {error && (
        <Text size="1" color="red">
          {error}
        </Text>
      )}
    </Flex>
  );
}

function SidebarNavContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();

  return (
    <>
      <Box px="4" py="5">
        <Text size="5" weight="bold">
          Clash Tracker
        </Text>
      </Box>
      <Flex direction="column" gap="1" px="2" className="flex-1 min-h-0 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const active =
            to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              onClick={() => onNavigate?.()}
              className={`flex items-center gap-3 rounded-md px-3 py-3 md:py-2 text-sm no-underline transition-colors touch-manipulation ${
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
      <Box className="border-t border-[var(--gray-5)] shrink-0" py="2" px="1">
        <Flex align="center" justify="between" gap="2" wrap="wrap" px="2">
          <ThemeToggle />
          <AdminToggle />
        </Flex>
      </Box>
    </>
  );
}

export function Layout() {
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  return (
    <Flex className="min-h-dvh min-h-screen flex-col md:flex-row">
      <nav
        className="hidden md:flex md:flex-col w-60 shrink-0 h-screen border-r border-[var(--gray-5)] bg-[var(--gray-2)]"
        aria-label="Main navigation"
      >
        <SidebarNavContent />
      </nav>

      {/* Native header: Radix Flex was overriding `md:hidden` so the mobile bar showed on desktop. */}
      <header
        className="flex md:hidden shrink-0 items-center justify-between gap-3 border-b border-[var(--gray-5)] bg-[var(--gray-2)] sticky top-0 z-10 px-4 py-3"
        style={{
          paddingTop: "max(0.75rem, env(safe-area-inset-top))",
          paddingLeft: "max(1rem, env(safe-area-inset-left))",
          paddingRight: "max(1rem, env(safe-area-inset-right))",
        }}
      >
        <Text size="4" weight="bold">
          Clash Tracker
        </Text>
        <Dialog.Root open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <Dialog.Trigger>
            <IconButton
              variant="ghost"
              color="gray"
              size="2"
              aria-label="Open menu"
            >
              <HamburgerMenuIcon width={20} height={20} />
            </IconButton>
          </Dialog.Trigger>
          <Dialog.Content
            aria-describedby={undefined}
            className="!fixed !inset-0 !left-0 !top-0 !transform-none !max-w-none w-screen max-w-[100vw] h-[100dvh] max-h-[100dvh] m-0 rounded-none flex flex-col p-0 overflow-hidden border-0 bg-[var(--gray-2)]"
            style={{
              width: "100vw",
              maxWidth: "100vw",
              height: "100dvh",
              maxHeight: "100dvh",
              paddingTop: "max(0.75rem, env(safe-area-inset-top))",
              paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))",
              paddingLeft: "max(1rem, env(safe-area-inset-left))",
              paddingRight: "max(1rem, env(safe-area-inset-right))",
            }}
          >
            <Flex align="center" justify="between" mb="3" px="1">
              <Dialog.Title className="m-0">
                <Text size="5" weight="bold">
                  Menu
                </Text>
              </Dialog.Title>
              <Dialog.Close>
                <IconButton variant="ghost" color="gray" size="2" aria-label="Close menu">
                  <Cross2Icon width={20} height={20} />
                </IconButton>
              </Dialog.Close>
            </Flex>
            <nav className="flex flex-col flex-1 min-h-0">
              <SidebarNavContent onNavigate={() => setMobileNavOpen(false)} />
            </nav>
          </Dialog.Content>
        </Dialog.Root>
      </header>

      <Box className="flex-1 min-h-0 overflow-auto p-4 md:p-6">
        <Outlet />
      </Box>
    </Flex>
  );
}
