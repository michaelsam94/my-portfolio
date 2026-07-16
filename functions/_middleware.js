const APEX_HOST = "michaelsam94.com";
const BLOG_HOST = "blog.michaelsam94.com";

// Match the static _headers HSTS policy. `Response.redirect()` produces a
// response with no custom headers, so 301s (www→apex, apex/blog normalization)
// would otherwise ship without HSTS and get flagged as "No HSTS support".
const HSTS = "max-age=63072000; includeSubDomains; preload";
function redirect(location, status = 301) {
  return new Response(null, {
    status,
    headers: { Location: location, "Strict-Transport-Security": HSTS },
  });
}

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
    /^\/[a-f0-9]{32}\.txt$/.test(pathname) ||
    // Google Search Console HTML verification (public/ → out/ root on apex).
    /^\/google[a-f0-9]+\.html$/.test(pathname)
  );
}

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const { hostname, pathname, search } = url;

  if (hostname === `www.${APEX_HOST}`) {
    if (isBlogPath(pathname)) {
      return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
    }
    url.hostname = APEX_HOST;
    url.protocol = "https:";
    return redirect(url.toString());
  }

  if (hostname === APEX_HOST && isBlogPath(pathname)) {
    // Leave /blog/assets on the apex deploy so case-study pages can load CSS/JS
    // without a cross-origin hop if they still reference the old path.
    if (pathname === "/blog/assets" || pathname.startsWith("/blog/assets/")) {
      return context.next();
    }
    return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
  }

  if (hostname === BLOG_HOST) {
    // Keep /blog/assets/* reachable without a redirect so styles/scripts never
    // depend on following a 301 (some clients are strict about that).
    if (pathname === "/blog/assets" || pathname.startsWith("/blog/assets/")) {
      return context.next();
    }

    if (isBlogPath(pathname)) {
      return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
    }

    if (!isRootPassthrough(pathname)) {
      const assetUrl = new URL(context.request.url);
      assetUrl.pathname = pathname === "/" ? "/blog/" : `/blog${pathname}`;
      return context.env.ASSETS.fetch(new Request(assetUrl.toString(), context.request));
    }
  }

  return context.next();
}
