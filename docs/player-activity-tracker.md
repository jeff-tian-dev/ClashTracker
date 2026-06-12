# Player activity — short context for narrative / storytelling (paste this)

Copy everything between the lines into another AI if you want it to describe “the activity tracker” accurately.

```
CONTEXT: Clash of Clans analytics app (Analytics-Dashboard).

What “activity tracker” means per player:
- On each player’s profile page there are two charts built from multiplayer OFFENSE only (defenses don’t count).
- Chart 1: last 7 local days — bar height = how many attacks fell in each clock hour (0–23) in the viewer’s timezone. Not exact science: it’s a vibe of when they tend to attack.
- Chart 2: calendar heatmap labelled “last 90 days” — one cell per local day; darker = more attacks that day. The colour scale is the same for everyone (buckets like 0, 1–4, 5–9, etc.).

Where the data comes from:
- A background job (~every 10 minutes) pulls each tracked player’s Clash battle log from Supercell, compares to a saved fingerprint, and records NEW offensive battles.
- Stored timestamps are when OUR system noticed the battle, NOT the real in-game battle time (the usable API doesn’t give reliable battle timestamps for this). So the charts are approximate “polling time” patterns.
- Old rows are deleted after ~90 days (same window as the heatmap). The hourly chart only uses the last 7 local days; daily squares on the heatmap keep their counts for the full 90-day period.

Who gets tracked:
- Members of tracked clans plus any “always tracked” player tags the admin pins.

Separate from Legends: same battle-log API feeds different database tables for trophy/Legends features; activity charts only use this “attack timestamps” pipeline.
```
