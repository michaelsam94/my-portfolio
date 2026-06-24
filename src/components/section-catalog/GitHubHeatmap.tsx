"use client";

import { useEffect, useRef, useState } from "react";

type ContributionDay = {
  date: string;
  count: number;
};

function level(count: number) {
  if (count === 0) return 0;
  if (count < 3) return 1;
  if (count < 8) return 2;
  if (count < 20) return 3;
  return 4;
}

export default function GitHubHeatmap({ days }: { days: ContributionDay[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedDay, setSelectedDay] = useState<ContributionDay | null>(days.at(-1) ?? null);
  const [activeDay, setActiveDay] = useState<ContributionDay | null>(days.at(-1) ?? null);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    node.scrollLeft = node.scrollWidth;
  }, []);

  return (
    <div className="activity-heatmap-wrap">
      <div className="activity-tooltip" role="status" aria-live="polite">
        {activeDay
          ? `${activeDay.date}: ${activeDay.count} commit${activeDay.count === 1 ? "" : "s"}`
          : "Hover, focus, or press a square."}
      </div>
      <div
        ref={scrollRef}
        className="activity-scroll"
        aria-label={`GitHub contribution activity from ${days[0]?.date} to ${days.at(-1)?.date}`}
      >
        <div className="activity-grid lifetime" onMouseLeave={() => setActiveDay(selectedDay)}>
          {days.map((day) => {
            const label = `${day.date}: ${day.count} commit${day.count === 1 ? "" : "s"}`;
            return (
              <button
                type="button"
                key={day.date}
                className={`activity-cell level-${level(day.count)}`}
                title={label}
                aria-label={label}
                aria-pressed={selectedDay?.date === day.date}
                onClick={() => {
                  setSelectedDay(day);
                  setActiveDay(day);
                }}
                onFocus={() => {
                  setSelectedDay(day);
                  setActiveDay(day);
                }}
                onMouseEnter={() => setActiveDay(day)}
                onPointerDown={() => {
                  setSelectedDay(day);
                  setActiveDay(day);
                }}
              />
            );
          })}
        </div>
        <div className="activity-selected" aria-hidden="true">
          Selected:{" "}
          {selectedDay
            ? `${selectedDay.date}: ${selectedDay.count} commit${selectedDay.count === 1 ? "" : "s"}`
            : "none"}
        </div>
      </div>
    </div>
  );
}
