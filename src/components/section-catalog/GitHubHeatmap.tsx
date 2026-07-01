"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const GITHUB_USERNAME = "michaelsam94";

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

function todayUtc() {
  return new Date().toISOString().slice(0, 10);
}

function addUtcDay(date: Date) {
  const next = new Date(date);
  next.setUTCDate(next.getUTCDate() + 1);
  return next;
}

function normalizeSnapshot(
  snapshot: ContributionSnapshot,
  source: string,
  fillMissingToToday = false,
): ContributionSnapshot {
  const days = [...(snapshot.contributionDays ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const last = days.at(-1)?.date;
  const today = todayUtc();

  if (fillMissingToToday && last && last < today) {
    let cursor = addUtcDay(new Date(`${last}T00:00:00Z`));
    while (cursor.toISOString().slice(0, 10) <= today) {
      days.push({ date: cursor.toISOString().slice(0, 10), count: 0 });
      cursor = addUtcDay(cursor);
    }
  }

  return {
    ...snapshot,
    contributionDays: days,
    source,
    totalContributions: snapshot.totalContributions ?? days.reduce((total, day) => total + day.count, 0),
  };
}

async function fetchSnapshot(url: string, source: string) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load contributions: ${response.status}`);
  return normalizeSnapshot((await response.json()) as ContributionSnapshot, source);
}

async function fetchLiveSnapshot() {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 4500);

  try {
    const response = await fetch(`/github-contributions?username=${encodeURIComponent(GITHUB_USERNAME)}`, {
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) throw new Error(`Failed to load live contributions: ${response.status}`);

    return normalizeSnapshot(
      (await response.json()) as ContributionSnapshot,
      "live GitHub contribution calendar",
      true,
    );
  } finally {
    window.clearTimeout(timeout);
  }
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
        const data = await fetchSnapshot("/contributions.json", "static snapshot, live refresh pending");
        if (!cancelled) {
          const latest = data.contributionDays?.at(-1) ?? null;
          setSnapshot(data);
          setSelectedDay(latest);
          setActiveDay(latest);
        }
      } catch {
        if (!cancelled) setLoadError(true);
        return;
      }

      try {
        const liveData = await fetchLiveSnapshot();
        if (!cancelled) {
          const latest = liveData.contributionDays?.at(-1) ?? null;
          setSnapshot(liveData);
          setSelectedDay(latest);
          setActiveDay(latest);
        }
      } catch {
        // Keep the static snapshot visible when a host has no function or the live refresh is slow.
      }
    }

    loadContributions();

    return () => {
      cancelled = true;
    };
  }, []);

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
    return <p className="activity-note">GitHub contribution activity could not be loaded.</p>;
  }

  if (!snapshot) {
    return <p className="activity-note">Loading live GitHub contribution activity...</p>;
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
        Full lifetime graph from {days[0]?.date ?? "account creation"} to {days.at(-1)?.date ?? "today"}. Source:{" "}
        {snapshot.source ?? "live GitHub contribution calendar"}.
      </p>
    </>
  );
}
