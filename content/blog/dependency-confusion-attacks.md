---
title: "Preventing Dependency Confusion Attacks"
slug: "dependency-confusion-attacks"
description: "How dependency confusion attacks hijack builds via package substitution — and the scoped packages, private registry config, and namespace controls that actually stop them."
datePublished: "2026-03-29"
dateModified: "2026-03-29"
tags: ["Security", "Supply Chain", "DevSecOps"]
keywords: "dependency confusion, package substitution, private registry, scoped packages, supply chain attack, namespace"
faq:
  - q: "What is a dependency confusion attack?"
    a: "A dependency confusion attack is a supply chain attack where an adversary publishes a malicious package to a public registry using the same name as one of your internal, private packages. When your package manager resolves dependencies, it may prefer the higher version number on the public registry over your private one, pulling the attacker's code into your build. It's also called package substitution or a namespace attack."
  - q: "How do attackers learn the names of my internal packages?"
    a: "Internal package names leak constantly — in committed lockfiles pushed to public repos, in error stack traces, in Docker image layers, in front-end bundles that reference internal module names, and in job postings that list internal tools. Once an attacker knows the name, publishing a public package with a high version number is trivial and cheap."
  - q: "Does using scoped packages fully prevent dependency confusion?"
    a: "Scoped packages (like @yourorg/utils) are a strong defense because the scope maps to a registry you control, but they aren't complete on their own. You still need registry configuration that binds the scope to your private registry, and you should combine scopes with explicit source pinning and namespace reservation on the public registry to close every gap."
---

In 2021 a security researcher earned six figures in bug bounties by uploading harmless packages to npm, PyPI, and RubyGems using names he'd scraped from the internal manifests of Apple, Microsoft, and dozens of other companies. Their build systems, given a choice between the real internal package and his public impostor with a higher version number, chose the impostor. That's dependency confusion in one sentence: your package manager fetches an attacker's public package because it shares a name with one of yours and looks "newer."

The attack is elegant precisely because nobody has to breach your network. The adversary just publishes to a registry you already trust and waits for your resolver to make the wrong call. I've reviewed enough CI pipelines to say this is still one of the most under-defended paths into a build, years after it went public.

## Why resolvers pick the wrong package

The root cause is version-based resolution across mixed sources. Many package managers, when configured to consult both a private registry and the public one, treat all sources as a single flat namespace and select the highest matching version. If your internal `@acme/auth-utils` sits at `1.4.2` privately and an attacker publishes `acme-auth-utils` at `99.0.0` publicly, a naive resolution grabs `99.0.0`.

The details differ by ecosystem, but the shape repeats:

- **npm** merges the default public registry with any configured private one unless you scope-map explicitly. Unscoped internal names are wide open.
- **pip** historically searched multiple indexes and could prefer whichever had the higher version, which is why `--index-url` versus `--extra-index-url` matters enormously.
- **Maven/Gradle** are safer by default because coordinates include a group ID, but mirror and repository ordering can still be misconfigured.

The common thread: whenever "where does this come from" is decided by version number instead of by an explicit source binding, you're exposed.

## Names leak — assume they're public

The uncomfortable premise is that your internal package names are not secret and never will be. They show up in lockfiles committed to public forks, in webpack bundles shipped to browsers, in stack traces posted to Stack Overflow, in `Dockerfile` layers, and in `package.json` files that slip into open-source repos. Treat every internal package name as if it's printed on your homepage, because effectively it is.

That reframing changes your defense strategy. You stop trying to hide names and start making the name *insufficient* to hijack the build. An attacker who knows the name should still be unable to substitute their code, because resolution is bound to a source you control.

## Defense one: scoped packages bound to a private registry

Scopes are the strongest structural fix in the npm world. A scoped name like `@acme/auth-utils` carries an organization namespace, and you configure the resolver to fetch that entire scope only from your registry.

```
# .npmrc — bind the @acme scope to the private registry, everything else to public
@acme:registry=https://registry.acme.internal/
//registry.acme.internal/:_authToken=${NPM_TOKEN}
registry=https://registry.npmjs.org/
```

Now `@acme/*` can never resolve to a public package, because the scope is nailed to a specific host. The equivalent discipline in Python is refusing to use `--extra-index-url` for internal packages and instead pointing at a single index that proxies public packages under your control:

```bash
# Don't do this — merges indexes and invites confusion:
pip install internal-lib --extra-index-url https://pypi.org/simple

# Do this — one index you control, which mirrors public packages:
pip install internal-lib --index-url https://pypi.acme.internal/simple --no-index-url-fallback
```

## Defense two: reserve your namespace publicly

Even with scopes, I reserve the organization's names on the public registries as a tripwire and a squat-block. Publishing a reserved `@acme` scope (or claiming the `acme-` prefix) on npm/PyPI means an attacker can't register a colliding public name in the first place. It costs an afternoon and removes an entire class of collision. Pair it with monitoring: alert when any package matching your naming patterns appears publicly, because that's either a mistake or an attack.

## Defense three: pin sources, not just versions

Lockfiles pin versions, but the security win comes from pinning *where each dependency resolves from*. Modern lockfiles record the resolved URL and an integrity hash; enforce them in CI with the strict, offline-ish install modes.

```bash
npm ci        # installs strictly from lockfile, fails on drift
pip install --require-hashes -r requirements.txt
```

`npm ci` refuses to silently upgrade or re-resolve, and `--require-hashes` makes pip reject any artifact whose hash doesn't match. This is the same integrity mindset that underpins [supply chain security with SLSA and SBOM](https://blog.michaelsam94.com/supply-chain-security-slsa-sbom/): you want a verifiable chain from "what I declared" to "what actually got installed," with no room for a substitute to slip in.

## Defense four: control the proxy and the pipeline

A single internal proxy registry (Artifactory, Nexus, Verdaccio, or a cloud artifact service) is the highest-leverage control. Configure it so that internal names resolve only to internally published artifacts and are *never* transparently fetched from upstream. Many teams enable "remote proxying" and accidentally let the proxy fetch an unknown internal name from the public mirror — which is exactly the hole you're trying to close. Set the priority so private always wins for your namespaces, and block upstream fetches for those patterns entirely.

The whole thing lives or dies in CI, so this belongs in your [shift-left DevSecOps](https://blog.michaelsam94.com/devsecops-shift-left/) checks: fail the build if resolution touches an unexpected registry, if an internal-looking name resolves from a public source, or if the lockfile drifts.

## A quick priority order

If you can only do a few things this quarter, here's how I'd sequence it:

1. Bind internal scopes/namespaces to your private registry in config, and enforce that config in CI.
2. Switch installs to lockfile-strict, hash-verified modes (`npm ci`, `--require-hashes`).
3. Reserve your namespaces on public registries and monitor for collisions.
4. Lock down the proxy so it never fetches internal names upstream.
5. Add SBOM generation so you can audit exactly what shipped, tying into [container image security and SBOMs](https://blog.michaelsam94.com/container-image-security-sbom/).

Dependency confusion is a cheap attack with an expensive blast radius — arbitrary code execution inside your build, with your build's credentials. The defenses are mostly configuration, not new tooling, which is the good news and the frustrating part: this keeps happening not because it's hard to stop, but because "highest version wins" is still the quiet default in too many pipelines.

## Resources

- [Alex Birsan — Dependency Confusion original research](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610)
- [npm docs — scopes and scoped packages](https://docs.npmjs.com/cli/v10/using-npm/scope)
- [Python Packaging — configuring package indexes](https://packaging.python.org/en/latest/guides/hosting-your-own-index/)
- [OWASP — Software Supply Chain Security](https://owasp.org/www-project-software-supply-chain-security/)
- [GitHub — Securing your software supply chain](https://docs.github.com/en/code-security/supply-chain-security)
- [SLSA — Supply-chain Levels for Software Artifacts](https://slsa.dev/)
