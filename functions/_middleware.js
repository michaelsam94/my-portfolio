const APEX_HOST = "michaelsam94.com";
const BLOG_HOST = "blog.michaelsam94.com";

function blogCleanPath(pathname) {
  const clean = pathname.replace(/^\/blog/, "") || "/";
  return clean.startsWith("/") ? clean : `/${clean}`;
}

function isBlogPath(pathname) {
  return pathname === "/blog" || pathname.startsWith("/blog/");
}

/** Root assets shared with the apex deploy; serve as-is on the blog host. */
function isRootPassthrough(pathname) {
  return (
    pathname.startsWith("/favicon") ||
    pathname === "/apple-touch-icon.png" ||
    pathname === "/site.webmanifest" ||
    pathname.startsWith("/og-image") ||
    pathname.startsWith("/profile-photo") ||
    pathname === "/robots.txt" ||
    // IndexNow key file lives at site root and must resolve on the blog host too.
    /^\/[a-f0-9]{32}\.txt$/.test(pathname)
  );
}

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const { hostname, pathname, search } = url;

  if (hostname === `www.${APEX_HOST}`) {
    if (isBlogPath(pathname)) {
      return Response.redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`, 301);
    }
    url.hostname = APEX_HOST;
    url.protocol = "https:";
    return Response.redirect(url.toString(), 301);
  }

  if (hostname === APEX_HOST && isBlogPath(pathname)) {
    // Leave /blog/assets on the apex deploy so case-study pages can load CSS/JS
    // without a cross-origin hop if they still reference the old path.
    if (pathname === "/blog/assets" || pathname.startsWith("/blog/assets/")) {
      return context.next();
    }
    return Response.redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`, 301);
  }

  if (hostname === BLOG_HOST) {
    // Keep /blog/assets/* reachable without a redirect so styles/scripts never
    // depend on following a 301 (some clients are strict about that).
    if (pathname === "/blog/assets" || pathname.startsWith("/blog/assets/")) {
      return context.next();
    }

    if (isBlogPath(pathname)) {
      return Response.redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`, 301);
    }

    if (!isRootPassthrough(pathname)) {
      const assetUrl = new URL(context.request.url);
      assetUrl.pathname = pathname === "/" ? "/blog/" : `/blog${pathname}`;
      return context.env.ASSETS.fetch(new Request(assetUrl.toString(), context.request));
    }
  }

  return context.next();
}
