export async function onRequest(context) {
  const url = new URL(context.request.url);

  if (url.hostname === "www.michaelsam94.com") {
    url.hostname = "michaelsam94.com";
    url.protocol = "https:";

    return Response.redirect(url.toString(), 301);
  }

  return context.next();
}
