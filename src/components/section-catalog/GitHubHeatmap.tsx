"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type ContributionDay = {
  date: string;
  count: number;
};

type ContributionSnapshot = {
  accountCreatedAt?: string;
  totalContributions?: number;
  contributionDays?: ContributionDay[];
  source?: string;
  generatedAt?: string;
};

const EMPTY_DAYS: ContributionDay[] = [];

function level(count: number) {
  if (count === 0) return 0;
  if (count < 3) return 1;
  if (count < 8) return 2;
  if (count < 20) return 3;
  return 4;
}

function commitLabel(day: ContributionDay) {
  return `${day.date}: ${day.count} commit${day.count === 1 ? "" : "s"}`;
}

export default function GitHubHeatmap() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [snapshot, setSnapshot] = useState<ContributionSnapshot | null>(null);
  const [loadError, setLoadError] = useState(false);
  const days = useMemo(() => snapshot?.contributionDays ?? EMPTY_DAYS, [snapshot]);
  const [selectedDay, setSelectedDay] = useState<ContributionDay | null>(null);
  const [activeDay, setActiveDay] = useState<ContributionDay | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadContributions() {
      try {
        const response = await fetch("/contributions.json");
        if (!response.ok) throw new Error(`Failed to load contributions: ${response.status}`);
        const data = (await response.json()) as ContributionSnapshot;
        if (!cancelled) setSnapshot(data);
      } catch {
        if (!cancelled) setLoadError(true);
      }
    }

    loadContributions();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const latest = days.at(-1) ?? null;
    setSelectedDay(latest);
    setActiveDay(latest);
  }, [days]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node || days.length === 0) return;
    node.scrollLeft = node.scrollWidth;
  }, [days]);

  const stats = useMemo(() => {
    const activeDays = days.filter((day) => day.count > 0).length;
    const lifetimeTotal = days.reduce((total, day) => total + day.count, 0);
    const recentTotal = days.slice(-365).reduce((total, day) => total + day.count, 0);
    const maxDay = days.reduce((max, day) => Math.max(max, day.count), 0);

    return {
      activeDays,
      lifetimeTotal,
      maxDay,
      recentTotal,
    };
  }, [days]);

  if (loadError) {
    return <p className="activity-note">GitHub contribution snapshot could not be loaded.</p>;
  }

  if (!snapshot) {
    return <p className="activity-note">Loading GitHub contribution activity...</p>;
  }

  return (
    <>
      <div className="activity-summary">
        <article>
          <strong>{snapshot.totalContributions ?? stats.lifetimeTotal}</strong>
          <span>lifetime contributions</span>
        </article>
        <article>
          <strong>{stats.recentTotal}</strong>
          <span>last 365 days</span>
        </article>
        <article>
          <strong>{stats.activeDays}</strong>
          <span>active days</span>
        </article>
        <article>
          <strong>{stats.maxDay}</strong>
          <span>max day</span>
        </article>
      </div>
      <div className="activity-heatmap-wrap">
        <div className="activity-tooltip" role="status" aria-live="polite">
          {activeDay ? commitLabel(activeDay) : "Hover, focus, or press a square."}
        </div>
        <div
          ref={scrollRef}
          className="activity-scroll"
          aria-label={`GitHub contribution activity from ${days[0]?.date} to ${days.at(-1)?.date}`}
        >
          <div className="activity-grid lifetime" onMouseLeave={() => setActiveDay(selectedDay)}>
            {days.map((day) => {
              const label = commitLabel(day);

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
        </div>
        <div className="activity-selected" aria-hidden="true">
          Selected: {selectedDay ? commitLabel(selectedDay) : "none"}
        </div>
      </div>
      <p className="activity-note">
        Full lifetime snapshot from {days[0]?.date ?? "account creation"} to {days.at(-1)?.date ?? "latest capture"}.
        Source: committed GitHub contribution snapshot
        {snapshot.generatedAt ? ` generated ${snapshot.generatedAt.slice(0, 10)}` : ""}.
      </p>
    </>
  );
}
