import { HashRouter, Routes, Route } from "react-router-dom";
import { AdminProvider } from "./lib/AdminContext";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Players } from "./pages/Players";
import { PlayerDetail } from "./pages/PlayerDetail";
import { Wars } from "./pages/Wars";
import { WarDetail } from "./pages/WarDetail";
import { Raids } from "./pages/Raids";
import { RaidDetail } from "./pages/RaidDetail";
import { TrackedClans } from "./pages/TrackedClans";

export default function App() {
  return (
    <AdminProvider>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/players" element={<Players />} />
            <Route path="/players/:tag" element={<PlayerDetail />} />
            <Route path="/wars" element={<Wars />} />
            <Route path="/wars/:id" element={<WarDetail />} />
            <Route path="/raids" element={<Raids />} />
            <Route path="/raids/:id" element={<RaidDetail />} />
            <Route path="/tracked-clans" element={<TrackedClans />} />
          </Route>
        </Routes>
      </HashRouter>
    </AdminProvider>
  );
}
