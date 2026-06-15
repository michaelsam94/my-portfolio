import { useEffect, useMemo, useRef, useState } from "react";
import "./OpenSource.css";

const GITHUB_USERNAME = "michaelsam94";

type GitHubRepo = {
  id: number;
  name: string;
  html_url: string;
  description: string | null;
  stargazers_count: number;
  forks_count: number;
  language: string | null;
  pushed_at: string;
  fork: boolean;
};

type GitHubIssue = {
  id: number;
  title: string;
  html_url: string;
  repository_url: string;
  state: string;
  updated_at: string;
};

type GitHubCommit = {
  sha: string;
  html_url: string;
  commit: {
    message: string;
    author: {
      date: string;
    };
  };
  repository?: {
    full_name: string;
  };
};

type ContributionDay = {
  date: string;
  count: number;
};

type OpenSourceData = {
  stars: number;
  totalContributions: number;
  pullRequests: number;
  issues: number;
  contributedRepos: number;
  commits: number;
  repos: GitHubRepo[];
  pullRequestItems: GitHubIssue[];
  commitItems: GitHubCommit[];
  contributionDays: ContributionDay[];
  source: "github-history" | "github-public-history" | "public-events";
};

type SearchResponse<T> = {
  total_count: number;
  items: T[];
};

type ContributionsFunctionResponse = {
  accountCreatedAt?: string;
  totalContributions?: number;
  commits?: number;
  pullRequests?: number;
  issues?: number;
  contributedRepos?: number;
  contributionDays?: ContributionDay[];
  source?: "github-history" | "github-public-history";
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function getRepoName(repositoryUrl: string) {
  return repositoryUrl.split("/repos/")[1] ?? "GitHub";
}

function startOfContributionYear() {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 1);
  date.setHours(0, 0, 0, 0);
  return date;
}

function buildEmptyContributionDays() {
  const start = startOfContributionYear();
  const end = new Date();
  const days: ContributionDay[] = [];

  for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
    days.push({ date: day.toISOString().slice(0, 10), count: 0 });
  }

  return days;
}

function mergeEventContributions(events: GitHubEvent[]) {
  const days = buildEmptyContributionDays();
  const byDate = new Map(days.map((day) => [day.date, day]));

  for (const event of events) {
    const date = event.created_at.slice(0, 10);
    const day = byDate.get(date);

    if (!day) {
      continue;
    }

    if (event.type === "PushEvent") {
      day.count += event.payload.commits?.length ?? 1;
    } else if (["PullRequestEvent", "IssuesEvent", "CreateEvent"].includes(event.type)) {
      day.count += 1;
    }
  }

  return days;
}

type GitHubEvent = {
  id: string;
  type: string;
  created_at: string;
  repo: {
    name: string;
  };
  payload: {
    commits?: Array<{ sha: string; message: string }>;
  };
};

async function githubFetch<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
    },
  });

  if (!response.ok) {
    throw new Error(`GitHub request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function fetchContributionDetails(username: string) {
  const response = await fetch(`/.netlify/functions/github-contributions?username=${username}`);

  if (!response.ok) {
    throw new Error("Contribution function unavailable");
  }

  return response.json() as Promise<ContributionsFunctionResponse>;
}

// Committed snapshot of the full history (scripts/fetch-contributions.mjs). Used when the
// live function is unavailable or rate-limited, so the graph still spans from account creation.
async function fetchStaticContributions(): Promise<ContributionsFunctionResponse | undefined> {
  try {
    const response = await fetch("/contributions.json");
    if (!response.ok) {
      return undefined;
    }
    return (await response.json()) as ContributionsFunctionResponse;
  } catch {
    return undefined;
  }
}

async function fetchOpenSourceData(): Promise<OpenSourceData> {
  const [
    repos,
    pullRequests,
    issues,
    commits,
    events,
    contributionDetails,
  ] = await Promise.all([
    githubFetch<GitHubRepo[]>(
      `https://api.github.com/users/${GITHUB_USERNAME}/repos?per_page=100&sort=pushed`,
    ),
    githubFetch<SearchResponse<GitHubIssue>>(
      `https://api.github.com/search/issues?q=author:${GITHUB_USERNAME}+type:pr&sort=updated&order=desc&per_page=6`,
    ),
    githubFetch<SearchResponse<GitHubIssue>>(
      `https://api.github.com/search/issues?q=author:${GITHUB_USERNAME}+type:issue&sort=updated&order=desc&per_page=1`,
    ),
    githubFetch<SearchResponse<GitHubCommit>>(
      `https://api.github.com/search/commits?q=author:${GITHUB_USERNAME}&sort=author-date&order=desc&per_page=6`,
    ).catch(() => ({ total_count: 0, items: [] })),
    githubFetch<GitHubEvent[]>(
      `https://api.github.com/users/${GITHUB_USERNAME}/events/public?per_page=100`,
    ).catch(() => []),
    fetchContributionDetails(GITHUB_USERNAME).catch(() => undefined),
  ]);

  const sourceRepos = repos.filter((repo) => !repo.fork);
  const stars = sourceRepos.reduce((total, repo) => total + repo.stargazers_count, 0);
  const eventRepos = new Set(events.map((event) => event.repo.name));
  const eventCommits = events.reduce((total, event) => {
    if (event.type !== "PushEvent") {
      return total;
    }

    return total + (event.payload.commits?.length ?? 0);
  }, 0);
  // Prefer the live function only when it returned real history (> ~1 year of days);
  // otherwise fall back to the committed full-history snapshot, then to recent events.
  const liveDays = contributionDetails?.contributionDays;
  const contributionDays =
    liveDays && liveDays.length >= 366
      ? liveDays
      : ((await fetchStaticContributions())?.contributionDays ?? liveDays ?? mergeEventContributions(events));

  return {
    stars,
    totalContributions:
      contributionDetails?.totalContributions ??
      contributionDays.reduce((total, day) => total + day.count, 0),
    pullRequests: contributionDetails?.pullRequests ?? pullRequests.total_count,
    issues: contributionDetails?.issues ?? issues.total_count,
    contributedRepos: contributionDetails?.contributedRepos ?? eventRepos.size,
    commits: contributionDetails?.commits ?? eventCommits,
    repos: sourceRepos.slice(0, 5),
    pullRequestItems: pullRequests.items,
    commitItems: commits.items,
    contributionDays,
    source: contributionDetails?.contributionDays
      ? contributionDetails.source ?? "github-history"
      : "public-events",
  };
}

function getContributionLevel(count: number) {
  if (count === 0) return "0";
  if (count < 2) return "1";
  if (count < 5) return "2";
  if (count < 10) return "3";
  return "4";
}

function useOpenSourceData() {
  const [data, setData] = useState<OpenSourceData | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let active = true;

    fetchOpenSourceData()
      .then((nextData) => {
        if (!active) return;
        setData(nextData);
        setStatus("ready");
      })
      .catch(() => {
        if (!active) return;
        setStatus("error");
      });

    return () => {
      active = false;
    };
  }, []);

  return { data, status };
}

type ContributionTooltip = {
  text: string;
  left: number;
  top: number;
};

function ContributionGraph({ days }: { days: ContributionDay[] }) {
  const [tooltip, setTooltip] = useState<ContributionTooltip | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const weeks = useMemo(() => {
    const padded = [...days];
    const firstDay = new Date(padded[0]?.date ?? new Date()).getDay();

    for (let i = 0; i < firstDay; i += 1) {
      padded.unshift({ date: "", count: 0 });
    }

    const grouped: ContributionDay[][] = [];
    for (let i = 0; i < padded.length; i += 7) {
      grouped.push(padded.slice(i, i + 7));
    }

    return grouped;
  }, [days]);

  // Weeks run oldest → newest left-to-right; show the most recent contributions by default.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const scrollToLatest = () => {
      el.scrollLeft = el.scrollWidth;
    };
    scrollToLatest();
    const raf = requestAnimationFrame(scrollToLatest);
    return () => cancelAnimationFrame(raf);
  }, [weeks]);

  const showTooltip = (day: ContributionDay, element: HTMLElement) => {
    if (!day.date) {
      return;
    }

    const rect = element.getBoundingClientRect();
    setTooltip({
      text: `${day.count} contributions on ${day.date}`,
      left: rect.left + rect.width / 2,
      top: rect.top,
    });
  };

  return (
    <div className="open-source-graph-wrap">
      <div className="open-source-graph" aria-label="GitHub contribution graph" ref={scrollRef}>
        {weeks.map((week, weekIndex) => (
          <div className="open-source-week" key={`week-${weekIndex}`}>
            {week.map((day, dayIndex) => (
              <span
                className="open-source-day"
                data-level={getContributionLevel(day.count)}
                key={`${day.date || weekIndex}-${dayIndex}`}
                aria-label={day.date ? `${day.count} contributions on ${day.date}` : undefined}
                data-count={day.date ? day.count : undefined}
                tabIndex={day.date ? 0 : -1}
                onBlur={() => setTooltip(null)}
                onFocus={(event) => showTooltip(day, event.currentTarget)}
                onMouseEnter={(event) => showTooltip(day, event.currentTarget)}
                onMouseLeave={() => setTooltip(null)}
                onMouseMove={(event) => showTooltip(day, event.currentTarget)}
              />
            ))}
          </div>
        ))}
      </div>
      {tooltip ? (
        <div
          className="open-source-tooltip"
          role="status"
          style={{ left: tooltip.left, top: tooltip.top }}
        >
          {tooltip.text}
        </div>
      ) : null}
    </div>
  );
}

export default function OpenSource() {
  const { data, status } = useOpenSourceData();

  return (
    <section className="open-source" id="open-source">
      <div className="open-source-inner">
        <div className="open-source-heading">
          <p className="section-kicker">Open Source</p>
          <h2>GitHub contribution activity</h2>
            <p>
            Recent public repositories, pull requests, commits, and a scrollable
            contribution view pulled from GitHub.
          </p>
        </div>

        {status === "loading" && (
          <div className="open-source-card open-source-loading">
            <span />
            <span />
            <span />
          </div>
        )}

        {status === "error" && (
          <div className="open-source-card open-source-error">
            GitHub activity is temporarily unavailable. The section will retry on the next visit.
          </div>
        )}

        {data && (
          <>
            <div className="open-source-stats" aria-label="GitHub contribution totals">
              <div className="open-source-card open-source-score-card">
                <div>
                  <h3>Michael Sam's GitHub Stats</h3>
                  <dl>
                    <div>
                      <dt>Total Stars Earned</dt>
                      <dd>{data.stars}</dd>
                    </div>
                    <div>
                      <dt>
                        Total Contributions{" "}
                        {data.source !== "public-events" ? "(lifetime)" : "(recent)"}
                      </dt>
                      <dd>{data.totalContributions}</dd>
                    </div>
                    <div>
                      <dt>
                        {data.source === "github-history"
                          ? "Commits (lifetime)"
                          : "Commits (recent)"}
                      </dt>
                      <dd>{data.commits}</dd>
                    </div>
                    <div>
                      <dt>Total PRs</dt>
                      <dd>{data.pullRequests}</dd>
                    </div>
                    <div>
                      <dt>Total Issues</dt>
                      <dd>{data.issues}</dd>
                    </div>
                    <div>
                      <dt>
                        Contributed to{" "}
                        {data.source === "github-history" ? "(lifetime)" : "(recent)"}
                      </dt>
                      <dd>{data.contributedRepos}</dd>
                    </div>
                  </dl>
                </div>
                <div className="open-source-grade" aria-label="GitHub activity grade">
                  B-
                </div>
              </div>

              <div className="open-source-card open-source-calendar-card">
                <div className="open-source-card-title">
                  <h3>Contribution graph</h3>
                  <span>
                    {data.source !== "public-events"
                      ? "Full account history"
                      : "Recent public events"}
                  </span>
                </div>
                <ContributionGraph days={data.contributionDays} />
              </div>
            </div>

            <div className="open-source-lists">
              <div className="open-source-card">
                <div className="open-source-card-title">
                  <h3>Recent repos</h3>
                  <a href={`https://github.com/${GITHUB_USERNAME}?tab=repositories`}>View all</a>
                </div>
                <ul className="open-source-list">
                  {data.repos.map((repo) => (
                    <li key={repo.id}>
                      <a href={repo.html_url} target="_blank" rel="noreferrer">
                        {repo.name}
                      </a>
                      <p>{repo.description ?? "Public repository"}</p>
                      <span>
                        {repo.language ?? "Code"} · {repo.stargazers_count} stars · updated{" "}
                        {formatDate(repo.pushed_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="open-source-card">
                <div className="open-source-card-title">
                  <h3>Recent pull requests</h3>
                  <a
                    href={`https://github.com/search?q=author%3A${GITHUB_USERNAME}+type%3Apr&type=pullrequests`}
                  >
                    View all
                  </a>
                </div>
                <ul className="open-source-list">
                  {data.pullRequestItems.map((pullRequest) => (
                    <li key={pullRequest.id}>
                      <a href={pullRequest.html_url} target="_blank" rel="noreferrer">
                        {pullRequest.title}
                      </a>
                      <span>
                        {getRepoName(pullRequest.repository_url)} · {pullRequest.state} · updated{" "}
                        {formatDate(pullRequest.updated_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="open-source-card">
                <div className="open-source-card-title">
                  <h3>Recent commits</h3>
                  <a
                    href={`https://github.com/search?q=author%3A${GITHUB_USERNAME}&type=commits`}
                  >
                    View all
                  </a>
                </div>
                <ul className="open-source-list">
                  {data.commitItems.length > 0 ? (
                    data.commitItems.map((commit) => (
                      <li key={commit.sha}>
                        <a href={commit.html_url} target="_blank" rel="noreferrer">
                          {commit.commit.message.split("\n")[0]}
                        </a>
                        <span>
                          {commit.repository?.full_name ?? "GitHub"} ·{" "}
                          {formatDate(commit.commit.author.date)}
                        </span>
                      </li>
                    ))
                  ) : (
                    <li>
                      <a href={`https://github.com/${GITHUB_USERNAME}`}>Commit search unavailable</a>
                      <span>GitHub occasionally rate-limits public commit search.</span>
                    </li>
                  )}
                </ul>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
