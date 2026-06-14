const GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql";

const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

const USER_QUERY = `
  query PortfolioUser($login: String!) {
    user(login: $login) {
      createdAt
    }
  }
`;

const CONTRIBUTIONS_QUERY = `
  query PortfolioContributionWindow($login: String!, $from: DateTime!, $to: DateTime!) {
    user(login: $login) {
      contributionsCollection(from: $from, to: $to) {
        totalCommitContributions
        totalPullRequestContributions
        totalIssueContributions
        commitContributionsByRepository(maxRepositories: 100) {
          repository {
            nameWithOwner
          }
        }
        contributionCalendar {
          weeks {
            contributionDays {
              date
              contributionCount
            }
          }
        }
      }
    }
  }
`;

async function githubGraphql(token, query, variables) {
  const response = await fetch(GITHUB_GRAPHQL_ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, variables }),
  });

  const payload = await response.json();

  if (!response.ok || payload.errors) {
    const status = response.status || 502;
    const message = payload.errors?.[0]?.message || "GitHub GraphQL request failed";
    throw Object.assign(new Error(message), { status });
  }

  return payload.data;
}

function addOneYear(date) {
  const next = new Date(date);
  next.setFullYear(next.getFullYear() + 1);
  return next;
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "michaelsam94-portfolio",
    },
  });

  if (!response.ok) {
    throw Object.assign(new Error("GitHub REST request failed"), { status: response.status });
  }

  return response.json();
}

function dateOnly(date) {
  return date.toISOString().slice(0, 10);
}

function buildContributionDays(fromDate, toDate, contributionDays) {
  const days = [];
  const cursor = new Date(dateOnly(fromDate));
  const end = new Date(dateOnly(toDate));

  while (cursor <= end) {
    const date = dateOnly(cursor);
    days.push({ date, count: contributionDays.get(date) ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }

  return days;
}

function parsePublicContributionCalendar(html) {
  const days = [];
  const dayPattern = /<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"[^>]*>/g;
  let match;

  while ((match = dayPattern.exec(html))) {
    const [, date, id] = match;
    const tooltipPattern = new RegExp(
      `<tool-tip[^>]*(?:for|data-for)="${id}"[^>]*>([\\s\\S]*?)<\\/tool-tip>`,
    );
    const tooltip = html.match(tooltipPattern)?.[1] ?? "";
    const text = tooltip.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    const countMatch = text.match(/([\d,]+) contributions?/i);
    const count = countMatch ? Number(countMatch[1].replace(/,/g, "")) : 0;

    days.push({ date, count });
  }

  return days;
}

async function loadPublicContributionHistory(username) {
  const user = await fetchJson(`https://api.github.com/users/${username}`);
  const createdAt = user.created_at;
  const now = new Date();
  let from = new Date(createdAt);
  const contributionDays = new Map();

  while (from < now) {
    const nextYear = addOneYear(from);
    const to = nextYear < now ? nextYear : now;
    const url = `https://github.com/users/${username}/contributions?from=${dateOnly(from)}&to=${dateOnly(to)}`;
    const response = await fetch(url, {
      headers: { "User-Agent": "michaelsam94-portfolio" },
    });

    if (!response.ok) {
      throw Object.assign(new Error("GitHub contribution calendar request failed"), {
        status: response.status,
      });
    }

    for (const day of parsePublicContributionCalendar(await response.text())) {
      contributionDays.set(day.date, day.count);
    }

    from = to;
  }

  const days = buildContributionDays(new Date(createdAt), now, contributionDays);
  const totalContributions = days.reduce((total, day) => total + day.count, 0);

  return {
    accountCreatedAt: createdAt,
    totalContributions,
    contributionDays: days,
  };
}

export const handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers };
  }

  const token = process.env.GITHUB_TOKEN;
  const username = event.queryStringParameters?.username || "michaelsam94";

  if (!token) {
    try {
      const publicHistory = await loadPublicContributionHistory(username);

      return {
        statusCode: 200,
        headers,
        body: JSON.stringify({
          ...publicHistory,
          source: "github-public-history",
        }),
      };
    } catch (error) {
      return {
        statusCode: error.status ?? 500,
        headers,
        body: JSON.stringify({ error: "Unable to load public GitHub contribution history" }),
      };
    }
  }

  try {
    const userData = await githubGraphql(token, USER_QUERY, { login: username });
    const createdAt = userData.user?.createdAt;

    if (!createdAt) {
      return {
        statusCode: 404,
        headers,
        body: JSON.stringify({ error: "GitHub user not found" }),
      };
    }

    const now = new Date();
    let from = new Date(createdAt);
    let commits = 0;
    let pullRequests = 0;
    let issues = 0;
    const repositories = new Set();
    const contributionDays = new Map();

    while (from < now) {
      const nextYear = addOneYear(from);
      const to = nextYear < now ? nextYear : now;
      const data = await githubGraphql(token, CONTRIBUTIONS_QUERY, {
        login: username,
        from: from.toISOString(),
        to: to.toISOString(),
      });

      const collection = data.user?.contributionsCollection;

      commits += collection?.totalCommitContributions ?? 0;
      pullRequests += collection?.totalPullRequestContributions ?? 0;
      issues += collection?.totalIssueContributions ?? 0;

      for (const repo of collection?.commitContributionsByRepository ?? []) {
        if (repo.repository?.nameWithOwner) {
          repositories.add(repo.repository.nameWithOwner);
        }
      }

      for (const week of collection?.contributionCalendar?.weeks ?? []) {
        for (const day of week.contributionDays ?? []) {
          contributionDays.set(day.date, day.contributionCount);
        }
      }

      from = to;
    }

    const days = buildContributionDays(new Date(createdAt), now, contributionDays);

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        accountCreatedAt: createdAt,
        totalContributions: days.reduce((total, day) => total + day.count, 0),
        commits,
        pullRequests,
        issues,
        contributedRepos: repositories.size,
        contributionDays: days,
      }),
    };
  } catch (error) {
    return {
      statusCode: error.status ?? 500,
      headers,
      body: JSON.stringify({ error: "Unable to load GitHub contributions" }),
    };
  }
};
