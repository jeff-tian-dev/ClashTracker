import { Flex, Text } from "@radix-ui/themes";
import {
  HEATMAP_DAY_COUNT,
  HEATMAP_LEVEL_CELL_CLASSES,
  LEVEL_LABELS,
  buildDailyCounts,
  buildHeatmapGrid,
} from "../lib/attackActivityHeatmap";

const CELL_PX = 12;
const GAP_PX = 2;

export function AttackActivityHeatmap({ attacks }: { attacks: { attacked_at: string }[] }) {
  const daily = buildDailyCounts(attacks, HEATMAP_DAY_COUNT);
  const grid = buildHeatmapGrid(daily, HEATMAP_DAY_COUNT);
  const colTemplate = `repeat(${grid.columnCount}, ${CELL_PX}px)`;
  const gapStyle = `${GAP_PX}px`;

  return (
    <Flex direction="column" gap="3">
      <Flex direction="column" gap="2">
        <Text size="3" weight="bold">
          Attack activity (last 90 days)
        </Text>
        <Text size="2" color="gray">
          One square per day in your local time. Darker colors mean more attacks; the scale is the same for every player.
        </Text>
      </Flex>

      <div className="overflow-x-auto pb-1 -mx-1 px-1">
        <Flex direction="column" gap="1" className="inline-flex min-w-0">
          <div
            className="grid w-max"
            style={{
              gridTemplateColumns: colTemplate,
              columnGap: gapStyle,
              rowGap: "2px",
            }}
          >
            {grid.monthLabels.map((lab, c) => (
              <div
                key={`m-${c}`}
                className="text-[10px] leading-none text-[var(--gray-11)] min-h-[14px] flex items-end"
              >
                {lab ?? "\u00a0"}
              </div>
            ))}
          </div>

          <div
            className="grid w-max"
            style={{
              gridAutoFlow: "column",
              gridTemplateColumns: colTemplate,
              gridTemplateRows: `repeat(7, ${CELL_PX}px)`,
              gap: gapStyle,
            }}
          >
            {Array.from({ length: grid.columnCount }, (_, c) =>
              Array.from({ length: 7 }, (_, r) => {
                const cell = grid.cells[c][r];
                if (!cell) {
                  return (
                    <div
                      key={`e-${c}-${r}`}
                      style={{ width: CELL_PX, height: CELL_PX }}
                      aria-hidden
                    />
                  );
                }
                const tip = `${cell.count} attack${cell.count === 1 ? "" : "s"} on ${cell.dateKey}`;
                const cls = HEATMAP_LEVEL_CELL_CLASSES[cell.level];
                return (
                  <div
                    key={cell.dateKey}
                    title={tip}
                    className={`${cls} w-[12px] h-[12px] shrink-0 opacity-95 hover:opacity-100 transition-opacity cursor-default`}
                    role="img"
                    aria-label={tip}
                  />
                );
              }),
            ).flat()}
          </div>
        </Flex>
      </div>

      <Flex align="center" gap="3" wrap="wrap" className="border-t border-[var(--gray-6)] pt-3">
        {LEVEL_LABELS.map((label, level) => (
          <Flex key={label} align="center" gap="1">
            <div
              className={`${HEATMAP_LEVEL_CELL_CLASSES[level]} w-[12px] h-[12px] shrink-0`}
              aria-hidden
            />
            <Text size="1" color="gray" className="tabular-nums">
              {label}
            </Text>
          </Flex>
        ))}
      </Flex>
    </Flex>
  );
}
