import { readFile } from "node:fs/promises";
import path from "node:path";
import GitHubHeatmap from "./GitHubHeatmap";

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

async function loadSnapshot(): Promise<ContributionSnapshot> {
  try {
    const raw = await readFile(path.join(process.cwd(), "public", "contributions.json"), "utf8");
    return JSON.parse(raw) as ContributionSnapshot;
  } catch {
    return {};
  }
}

export default async function GitHubActivity() {
  const snapshot = await loadSnapshot();
  const days = snapshot.contributionDays ?? [];
  const activeDays = days.filter((day) => day.count > 0).length;
  const lifetimeTotal = days.reduce((total, day) => total + day.count, 0);
  const recentDays = days.slice(-365);
  const recentTotal = recentDays.reduce((total, day) => total + day.count, 0);
  const maxDay = days.reduce((max, day) => Math.max(max, day.count), 0);

  return (
    <div className="activity-panel">
      <div className="activity-summary">
        <article>
          <strong>{snapshot.totalContributions ?? lifetimeTotal}</strong>
          <span>lifetime contributions</span>
        </article>
        <article>
          <strong>{recentTotal}</strong>
          <span>last 365 days</span>
        </article>
        <article>
          <strong>{activeDays}</strong>
          <span>active days</span>
        </article>
        <article>
          <strong>{maxDay}</strong>
          <span>max day</span>
        </article>
      </div>
      <GitHubHeatmap days={days} />
      <p className="activity-note">
        Full lifetime snapshot from {days[0]?.date ?? "account creation"} to {days.at(-1)?.date ?? "latest capture"}.
        Source: committed GitHub contribution snapshot{snapshot.generatedAt ? ` generated ${snapshot.generatedAt.slice(0, 10)}` : ""}.
      </p>
    </div>
  );
}
