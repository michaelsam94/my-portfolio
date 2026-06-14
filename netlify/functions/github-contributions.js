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

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers };
  }

  const token = process.env.GITHUB_TOKEN;
  const username = event.queryStringParameters?.username || "michaelsam94";

  if (!token) {
    return {
      statusCode: 503,
      headers,
      body: JSON.stringify({ error: "GITHUB_TOKEN is not configured" }),
    };
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

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        accountCreatedAt: createdAt,
        commits,
        pullRequests,
        issues,
        contributedRepos: repositories.size,
        contributionDays: Array.from(contributionDays, ([date, count]) => ({ date, count }))
          .sort((a, b) => a.date.localeCompare(b.date)),
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
