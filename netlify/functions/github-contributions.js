import { onRequest } from "../../functions/github-contributions.js";

export async function handler(event) {
  const query = event.rawQuery ? `?${event.rawQuery}` : "";
  const request = new Request(`https://${event.headers.host || "michaelsam94.com"}/github-contributions${query}`, {
    method: event.httpMethod,
    headers: event.headers,
  });

  const response = await onRequest({
    request,
    env: process.env,
  });

  const headers = Object.fromEntries(response.headers.entries());

  return {
    statusCode: response.status,
    headers,
    body: await response.text(),
  };
}
