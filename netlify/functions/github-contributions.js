const GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql";

const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

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

  const to = new Date();
  const from = new Date(to);
  from.setFullYear(from.getFullYear() - 1);

  const query = `
    query PortfolioContributions($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalRepositoriesWithContributedCommits
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

  try {
    const response = await fetch(GITHUB_GRAPHQL_ENDPOINT, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        variables: {
          login: username,
          from: from.toISOString(),
          to: to.toISOString(),
        },
      }),
    });

    const payload = await response.json();

    if (!response.ok || payload.errors) {
      return {
        statusCode: response.status || 502,
        headers,
        body: JSON.stringify({ error: "GitHub GraphQL request failed" }),
      };
    }

    const collection = payload.data?.user?.contributionsCollection;
    const contributionDays =
      collection?.contributionCalendar?.weeks?.flatMap((week) =>
        week.contributionDays.map((day) => ({
          date: day.date,
          count: day.contributionCount,
        })),
      ) ?? [];

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        commits: collection?.totalCommitContributions ?? 0,
        pullRequests: collection?.totalPullRequestContributions ?? 0,
        issues: collection?.totalIssueContributions ?? 0,
        contributedRepos: collection?.totalRepositoriesWithContributedCommits ?? 0,
        contributionDays,
      }),
    };
  } catch (error) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: "Unable to load GitHub contributions" }),
    };
  }
};
