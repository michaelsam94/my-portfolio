const APEX_HOST = "michaelsam94.com";
const BLOG_HOST = "blog.michaelsam94.com";
const NATEGA_HOST = "natega.michaelsam94.com";
const HSTS = "max-age=63072000; includeSubDomains; preload";
const GOOGLE_VERIFICATION_PATH = "/google42b4c336817b4c5e.html";
const GOOGLE_VERIFICATION_BODY = "google-site-verification: google42b4c336817b4c5e.html";

function redirect(location, status = 301) {
  return new Response(null, {
    status,
    headers: { Location: location, "Strict-Transport-Security": HSTS },
  });
}

function isBlogPath(pathname) {
  return pathname === "/blog" || pathname.startsWith("/blog/");
}

function blogCleanPath(pathname) {
  const clean = pathname.replace(/^\/blog/, "") || "/";
  return clean.startsWith("/") ? clean : `/${clean}`;
}

function isSharedRootAsset(pathname) {
  return (
    pathname.startsWith("/favicon") ||
    pathname === "/apple-touch-icon.png" ||
    pathname === "/site.webmanifest" ||
    pathname.startsWith("/og-image") ||
    pathname.startsWith("/profile-photo") ||
    pathname === "/robots.txt" ||
    /^\/[a-f0-9]{32}\.txt$/.test(pathname) ||
    /^\/google[a-f0-9]+\.html$/.test(pathname)
  );
}

function fetchAsset(request, env, pathname) {
  const assetUrl = new URL(request.url);
  assetUrl.pathname = pathname;
  return env.ASSETS.fetch(new Request(assetUrl.toString(), request));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { hostname, pathname, search } = url;

    if (hostname.endsWith(".pages.dev")) {
      return redirect(`https://${APEX_HOST}${pathname}${search}`);
    }

    if (hostname === `www.${APEX_HOST}`) {
      if (isBlogPath(pathname)) {
        return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
      }
      return redirect(`https://${APEX_HOST}${pathname}${search}`);
    }

    if (hostname === NATEGA_HOST) {
      if (pathname === GOOGLE_VERIFICATION_PATH) {
        return new Response(GOOGLE_VERIFICATION_BODY, {
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "public, max-age=300",
            "Strict-Transport-Security": HSTS,
          },
        });
      }

      if (pathname === "/") return fetchAsset(request, env, "/natega/");
      if (pathname === "/en" || pathname === "/en/") return fetchAsset(request, env, "/en/natega/");
      if (pathname === "/franko" || pathname === "/franko/") {
        return fetchAsset(request, env, "/franko/natega/");
      }
      if (pathname === "/robots.txt") return fetchAsset(request, env, "/natega-robots.txt");
      if (pathname === "/sitemap.xml") return fetchAsset(request, env, "/natega-sitemap.xml");

      return env.ASSETS.fetch(request);
    }

    if (hostname === BLOG_HOST) {
      if (isBlogPath(pathname)) {
        return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
      }
      if (!isSharedRootAsset(pathname)) {
        return fetchAsset(request, env, pathname === "/" ? "/blog/" : `/blog${pathname}`);
      }
      return env.ASSETS.fetch(request);
    }

    if (hostname === APEX_HOST) {
      // Serve the exact no-slash URL directly so Googlebot never encounters
      // Next's automatic 308 while inspecting the former canonical path.
      if (pathname === "/natega") return fetchAsset(request, env, "/natega/");

      if (isBlogPath(pathname)) {
        if (pathname === "/blog/assets" || pathname.startsWith("/blog/assets/")) {
          return env.ASSETS.fetch(request);
        }
        return redirect(`https://${BLOG_HOST}${blogCleanPath(pathname)}${search}`);
      }

      // Preserve the existing endpoint with the committed contribution snapshot
      // when Pages Functions are not bundled by the Cloudflare deployment.
      if (pathname === "/github-contributions") {
        return fetchAsset(request, env, "/contributions.json");
      }
    }

    return env.ASSETS.fetch(request);
  },
};
