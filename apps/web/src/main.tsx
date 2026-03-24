import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { Theme } from "@radix-ui/themes";
import App from "./App";
import { ThemePreferenceProvider, useThemePreference } from "./lib/ThemePreferenceContext";
import "./index.css";

function ThemedApp() {
  const { appearance } = useThemePreference();
  useEffect(() => {
    document.documentElement.style.colorScheme = appearance === "dark" ? "dark" : "light";
  }, [appearance]);
  return (
    <Theme
      accentColor="amber"
      grayColor="sand"
      radius="medium"
      scaling="100%"
      appearance={appearance}
      hasBackground
    >
      <App />
    </Theme>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemePreferenceProvider>
      <ThemedApp />
    </ThemePreferenceProvider>
  </React.StrictMode>
);
