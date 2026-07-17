# Part 1: SEO (2) + Serverless DB + Room KMP + Supply chain + Technical writing

POSTS = {}

POSTS["seo-javascript-rendering-crawl"] = (
    {
        "title": "JavaScript Rendering and Crawl Budget",
        "description": "Google renders JS but crawl budget is finite — SSR vs CSR for indexable content and rendering diagnostics.",
        "datePublished": "2026-10-02",
        "tags": ["SEO", "SSR", "Crawling"],
        "keywords": "JavaScript SEO rendering, crawl budget SPA, Googlebot rendering",
        "faq": [
            {
                "q": "Does Google fully render JavaScript before indexing?",
                "a": "Googlebot queues JavaScript rendering in a separate pass after the initial HTML fetch. Most pages get rendered, but rendering is resource-limited and not instantaneous. Critical indexable content should appear in the initial HTML response or be reliably server-rendered so you are not dependent on a second crawl wave.",
            },
            {
                "q": "When should a SPA use SSR or prerendering for SEO?",
                "a": "Use SSR, SSG, or prerendering for any URL you want indexed that currently shows an empty shell until client JS runs. Marketing pages, product catalogs, and blog posts should ship meaningful HTML. Authenticated app shells behind login can remain CSR because they should be noindex anyway.",
            },
            {
                "q": "How do I diagnose JavaScript rendering problems in Search Console?",
                "a": "Use URL Inspection and compare the rendered HTML to what users see. Check the Page indexing report for 'Crawled — currently not indexed' on JS-heavy URLs. Pair with Rich Results Test and server logs showing Googlebot Smartphone user-agent hits returning thin HTML.",
            },
        ],
    },
    r"""Search Console showed 40,000 product URLs as "Crawled — currently not indexed." View-source on any URL returned `<div id="root"></div>` and a 1.2 MB JavaScript bundle. Googlebot did render the pages eventually — the crawl log proved it — but rendering happened in a second wave days later, and the crawl budget for that wave was already spent on faceted filter URLs. JavaScript SEO is not a question of whether Google *can* run your bundle. It is a question of whether you can afford to wait while it does.

## How Googlebot processes JavaScript sites

Google's pipeline has distinct stages: discovery, crawl, render, index. A client-rendered React app often passes crawl with almost no indexable text. The renderer then executes JavaScript in a headless Chromium environment comparable to evergreen Chrome, but with limits on CPU time, network fetches, and queue depth.

```
Discovery → Crawl HTML → Render queue → Execute JS → Index
                │                              │
                └── thin HTML here              └── content appears here (maybe)
```

| Signal | What it means | Action |
|--------|---------------|--------|
| HTML has `<title>` and body text | Fast path to index | Keep monitoring CWV |
| HTML is empty shell | Depends on render queue | SSR critical content |
| Rendered HTML differs from user view | Hydration or geo bugs | Fix SSR/client mismatch |
| High crawl, low index ratio | Budget waste on low-value URLs | noindex faceted URLs |

Crawl budget — the rate and depth Google crawls your site — is finite for most domains. When Google spends renders on infinite filter combinations, product pages wait. That is why enterprise SPAs migrate indexable routes to SSR or static generation even though client rendering "works" in manual tests.

## SSR, SSG, and hybrid patterns

**Server-Side Rendering (SSR)** generates HTML per request. Best for personalized or frequently changing catalog pages where static export is impractical.

**Static Site Generation (SSG)** pre-renders at build time. Ideal for marketing and docs with predictable paths.

**Incremental Static Regeneration (ISR)** combines static speed with background revalidation — common in Next.js for large product catalogs.

```tsx
// Next.js App Router: server component fetches SEO-critical data
export default async function ProductPage({ params }: { params: { slug: string } }) {
  const product = await getProduct(params.slug); // runs on server
  return (
    <>
      <h1>{product.name}</h1>
      <p>{product.description}</p>
      <AddToCartButton productId={product.id} /> {/* client component */}
    </>
  );
}
```

The rule: **anything you want indexed should exist in the first HTML byte stream**. Client components can enhance interactivity after hydration, but they should not be the sole source of headings, prices, or canonical link tags.

For legacy SPAs where full SSR migration is expensive, **dynamic rendering** (serving prerendered HTML to bots only) still exists as a bridge. Google prefers consistent content between users and bots; use bot-specific rendering only as temporary technical debt with a migration plan.

## Rendering diagnostics that actually help

**URL Inspection** in Search Console shows fetched HTML, rendered HTML, and screenshot. Diff them. If rendered HTML contains product names but fetched HTML does not, you are render-dependent.

**Rich Results Test** validates structured data after rendering — JSON-LD injected only on the client will fail validation against raw HTML.

Log Googlebot user agents separately and alert when HTML response size drops below a threshold (symptom of accidental CSR regression):

```nginx
# nginx: flag thin HTML responses to Googlebot
map $http_user_agent $is_googlebot {
    default 0;
    ~*Googlebot 1;
}
log_format googlebot '$remote_addr "$request" $status $body_bytes_sent "$http_user_agent"';
```

**Lighthouse "Disable JavaScript"** audit quickly shows whether meaningful content survives without JS — a rough proxy for crawl-time visibility.

## Crawl budget hygiene for JS sites

Infinite client routes are invisible to users until clicked but discoverable via internal links and sitemaps. Common budget drains:

- Faceted navigation generating `?color=red&size=xl&sort=price` combinations
- Calendar widgets exposing every date as a crawlable URL
- API-driven pagination without `rel=next/prev` or canonical consolidation

Combine **canonical tags** on parameterized URLs, **noindex** on thin variants, and **robots.txt** only for URLs you never want crawled (remember: robots.txt blocks crawl, not indexing if links exist elsewhere).

```html
<link rel="canonical" href="https://example.com/products/widget" />
<meta name="robots" content="noindex, follow" /> <!-- on filter pages only -->
```

## Core Web Vitals interact with rendering

Heavy JavaScript hurts INP and LCP. Google uses page experience signals; slow render queues correlate with poor CWV. Code-splitting, deferring non-critical scripts, and server-rendering above-the-fold content improve both UX and crawl efficiency.

Measure field data in CrUX before and after SSR migration on a representative URL set. Lab scores alone lie when real users on mid-tier Android devices hydrate 900 KB of vendor chunks.

## Migration checklist

1. Inventory indexable URLs and classify: marketing (SSG), catalog (SSR/ISR), app (noindex).
2. Ensure `<title>`, meta description, canonical, and H1 appear in server HTML.
3. Verify JSON-LD in server output, not post-hydration only.
4. Compare URL Inspection rendered vs browser DevTools disable-JS view.
5. Monitor indexed count and crawl stats weekly for eight weeks post-launch.
6. Block or noindex low-value parameterized URLs before chasing "more rendering."

## Common mistakes

- Assuming "Google executes React" means CSR is fine for ecommerce PLPs.
- Testing with `curl` only — no JS execution, false confidence.
- Hydration mismatch causing Google to see different text than users (cloaking risk).
- Shipping `loading="lazy"` on LCP hero images without priority hints.
- Deploying SSR for bots only with different prices or content — policy violation.

JavaScript rendering capability removed the old hard blocker for SPAs in search. Crawl budget and render queue latency replaced it. Teams that treat HTML as the contract for indexable content — and JavaScript as enhancement — index faster, debug easier, and stop burning renders on empty shells.""",
)

POSTS["seo-meta-robots-noindex-patterns"] = (
    {
        "title": "Meta Robots and noindex Patterns",
        "description": "noindex for staging, faceted search, and thin pages — robots meta vs X-Robots-Tag and crawl budget.",
        "datePublished": "2026-09-24",
        "tags": ["SEO", "Meta Tags", "Indexing"],
        "keywords": "meta robots noindex, X-Robots-Tag, crawl budget",
        "faq": [
            {
                "q": "What is the difference between robots meta and X-Robots-Tag?",
                "a": "Both communicate indexing directives to crawlers. The robots meta tag lives in HTML head. X-Robots-Tag is an HTTP response header useful for non-HTML resources like PDFs, images, or JSON responses, and for applying site-wide rules at the CDN without touching page templates.",
            },
            {
                "q": "Can noindex pages still consume crawl budget?",
                "a": "Yes. Google must crawl a URL to read noindex. The directive prevents indexing, not discovery or crawling. For large low-value URL spaces, combine noindex with internal link reduction, canonicalization, or blocking crawl via robots.txt when appropriate — understanding robots.txt does not guarantee de-indexing of already-known URLs.",
            },
            {
                "q": "Should staging environments use noindex or authentication?",
                "a": "Use both. noindex, nofollow on staging is necessary but not sufficient — staging URLs leak via DNS, emails, and misconfigured sitemaps. Require authentication, disallow in robots.txt, and avoid linking from production. Treat noindex as a safety net, not a perimeter fence.",
            },
        ],
    },
    r"""A staging deploy indexed 12,000 SKUs with `price: $0.00` because someone copied production `robots.txt` but forgot the `<meta name="robots">` on the preview subdomain. Google Search Console flagged duplicate content; paid search quality score dropped for two weeks. Meta robots directives are small strings with outsized blast radius. Used correctly, they sculpt crawl toward money pages. Used casually, they leak staging, hide canonical products, or fight themselves against sitemap entries.

## Directives and syntax

Common robots meta values:

| Directive | Effect |
|-----------|--------|
| `index` / `noindex` | Allow or prevent storing in search index |
| `follow` / `nofollow` | Pass or withhold link equity from outbound links |
| `none` | Equivalent to `noindex, nofollow` |
| `noarchive` | Omit cached snippet link |
| `nosnippet` | No text snippet in results |
| `max-snippet:N` | Limit snippet length |

HTML form:

```html
<meta name="robots" content="noindex, follow" />
```

HTTP header form (same semantics):

```http
X-Robots-Tag: noindex, follow
```

Headers win for assets without `<head>`:

```nginx
location ~* \.(pdf|zip)$ {
    add_header X-Robots-Tag "noindex, noarchive" always;
}
```

Google supports `noindex` in robots.txt for supported user agents as of recent updates, but meta and headers remain the portable baseline across Bing and other engines.

## Pattern: staging and preview hosts

**Goal:** Never index non-production content.

```html
<!-- staging.example.com template -->
<meta name="robots" content="noindex, nofollow" />
```

Add defense in depth:

```txt
# staging.example.com/robots.txt
User-agent: *
Disallow: /
```

Configure CDN/WAF to require SSO on preview hosts. Remove staging from public DNS where possible; use internal-only hostnames. CI should fail if production sitemap URLs resolve to staging IPs.

## Pattern: faceted and filtered catalog URLs

Faceted search generates combinatorial URLs — `/shoes?brand=nike&color=red&size=10`. Most combinations are thin or duplicate.

Strategy ladder:

1. **Canonical** to master category URL when filters are cosmetic.
2. **noindex, follow** on filter combinations you allow users to share but do not want indexed.
3. **Disallow** crawl of deep parameter patterns in robots.txt when internal links are controlled.

```tsx
// Next.js: noindex deep filter pages
export async function generateMetadata({ searchParams }) {
  const filterCount = Object.keys(searchParams).length;
  return {
    robots: filterCount > 1 ? { index: false, follow: true } : { index: true, follow: true },
  };
}
```

Do not noindex paginated series incorrectly — page 2+ of unique content may deserve index with self-referencing canonicals.

## Pattern: thin and utility pages

Login, cart, checkout, internal search results, print-friendly views, and tag pages with one post often qualify for noindex. Ask: "Would a user landing from Google be served?" If the page is a gateway, noindex.

Account dashboards behind auth should still carry noindex as belt-and-suspenders when session bugs occasionally expose content.

## Pattern: syndicated and duplicate content

When you republish partner content with permission, either canonical to the source or noindex your copy. Dual-indexed syndication triggers duplicate clustering; you may not rank either version.

## X-Robots-Tag at the edge

Edge headers centralize policy without redeploying every template:

```javascript
// Cloudflare Worker sketch
export async function onRequest(context) {
  const response = await context.next();
  const url = new URL(context.request.url);
  if (url.pathname.startsWith("/api/")) {
    response.headers.set("X-Robots-Tag", "noindex");
  }
  if (url.hostname.startsWith("staging.")) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}
```

Useful when marketing owns CMS templates but platform owns `/api/*` and static asset routes.

## Conflicts to avoid

| Mistake | Symptom |
|---------|---------|
| noindex + sitemap inclusion | Wasted crawl, conflicting signals |
| noindex + internal prominence | Google crawls repeatedly, never indexes |
| robots.txt Disallow + need to noindex | Cannot read noindex if not crawled — old URLs linger |
| Production noindex typo | Whole site drops from index within days |

Audit sitemaps monthly: every URL should be indexable intent. Remove noindex URLs from sitemaps immediately.

## Monitoring

- Search Console **Page indexing** report: track "Excluded by noindex tag."
- Alert on indexed URL count drops exceeding seasonal baseline.
- Crawl log analysis: high crawl rate on noindex URLs signals internal link bloat.
- Staging DNS monitoring: public resolution triggers pager.

## Decision framework

Ask four questions before adding noindex:

1. Should this URL ever rank for a query?
2. Does it duplicate another URL we prefer?
3. Is it valuable to users only in-session (not as landing page)?
4. Are we trying to save crawl budget on low-value variants?

If "no" to ranking and "yes" to duplicate or session-only, noindex is appropriate. If the content is unique and commercially valuable, fix quality and canonicals instead of noindexing.

Meta robots is not a substitute for information architecture. It is the fine brush after structure — keeping staging dark, filters controlled, and crawl focused on pages that earn traffic.""",
)

POSTS["serverless-database-access-patterns"] = (
    {
        "title": "Database Access from Serverless",
        "description": "Connect serverless functions to databases safely: RDS Proxy, connection pooling, IAM auth, and patterns that avoid exhausting max connections.",
        "datePublished": "2025-07-18",
        "tags": ["Serverless", "Database", "AWS Lambda", "Architecture"],
        "keywords": "serverless database access, RDS Proxy Lambda, connection pooling serverless, Lambda PostgreSQL connections, DynamoDB serverless, IAM database authentication",
        "faq": [
            {
                "q": "Why do Lambda functions exhaust database connections?",
                "a": "Each concurrent invocation may open its own TCP connection to Postgres or MySQL. Lambda scales concurrency quickly—500 invocations can mean 500 connections against a db.t3.medium with max_connections around 100. Traditional app-server pools assume long-lived processes; Lambda's ephemeral model needs pooling at a shared layer or a connectionless datastore.",
            },
            {
                "q": "When should I use RDS Proxy versus PgBouncer?",
                "a": "RDS Proxy integrates with IAM auth, Secrets Manager rotation, and Aurora failover for AWS-native stacks. PgBouncer on ECU or ECS suits multi-cloud or self-managed Postgres with mature pool tuning. Both multiplex many client connections onto fewer database connections; pick based on ops model and auth requirements.",
            },
            {
                "q": "Is DynamoDB always better for serverless?",
                "a": "DynamoDB eliminates connection management and scales with pay-per-request, ideal for key-value and simple access patterns. Relational queries, complex joins, and existing ORM investments may justify RDS with Proxy. Hybrid architectures use Dynamo for hot paths and RDS for reporting via streams.",
            },
        ],
    },
    r"""CloudWatch showed `FATAL: too many connections for role "app"` ninety seconds after a marketing email dropped. Five hundred Lambdas each opened a fresh Postgres connection because someone copied a Flask SQLAlchemy snippet into `handler.py`. Serverless compute scales horizontally by default; relational databases scale connections vertically with hard ceilings. The fix is never "cap Lambda concurrency at 20" on a revenue path — it is architecture that matches ephemeral workers to durable connection budgets.

## The connection math

Postgres `max_connections` on a small RDS instance might be 100–200. Aurora raises limits but not infinitely. Lambda concurrency can hit account limits in the thousands.

```
500 concurrent Lambdas × 1 connection each = 500 DB connections → outage
500 concurrent Lambdas → RDS Proxy → ~30 pooled DB connections → survives
```

| Approach | Connections from Lambda | Ops complexity |
|----------|-------------------------|----------------|
| Direct connect per invoke | 1:1 with concurrency | Low code, high outage risk |
| Reuse in execution context | 1 per warm container | Helps, insufficient alone |
| RDS Proxy / PgBouncer | Multiplexed | Medium — required at scale |
| HTTP Data API / DynamoDB | None (TCP to DB) | Different data model |

## RDS Proxy pattern

RDS Proxy sits between Lambda and Aurora/RDS, maintaining a warm pool and handling failover pin-off.

```python
import os
import psycopg2
from aws_lambda_powertools import Logger

logger = Logger()
_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            host=os.environ["PROXY_ENDPOINT"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            sslmode="require",
            connect_timeout=3,
        )
    return _conn

def handler(event, context):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, email FROM users WHERE id = %s", (event["userId"],))
        row = cur.fetchone()
    return {"userId": row[0], "email": row[1]}
```

**Always close cursors quickly**; return connections to the proxy pool. Set **`statement_timeout`** and **`idle_in_transaction_session_timeout`** on the database so stuck Lambdas release slots.

Enable **IAM database authentication** to eliminate long-lived passwords in environment variables:

```python
import boto3

def iam_token():
    rds = boto3.client("rds")
    return rds.generate_db_auth_token(
        DBHostname=os.environ["PROXY_ENDPOINT"],
        Port=5432,
        DBUsername=os.environ["DB_USER"],
        Region=os.environ["AWS_REGION"],
    )
```

Rotate Secrets Manager credentials through Proxy without redeploying every function when not using IAM auth.

## Warm container reuse — necessary but not sufficient

Lambda reuses execution environments. A module-level connection survives across invocations on the same instance — reducing handshake overhead. At spike concurrency, new instances still open new connections. Never rely on reuse alone; Proxy is mandatory for unpredictable traffic.

Watch **DatabaseConnections** CloudWatch metric and Proxy **ClientConnections** vs **DatabaseConnectionsCurrentlyInUse**.

## HTTP and connectionless alternatives

**RDS Data API** (HTTP JSON interface to Aurora Serverless) removes persistent TCP from Lambda at the cost of latency and feature gaps (no LISTEN, limited session semantics).

**PostgREST** or **Hasura** behind API Gateway gives HTTP SQL with auth — connection pooling lives on the service layer.

**DynamoDB** fits event-driven, key-value access:

```python
import boto3
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb")
table = ddb.Table("Users")

def handler(event, context):
    resp = table.get_item(Key={"pk": f"USER#{event['userId']}", "sk": "PROFILE"})
    return resp.get("Item", {})
```

Design single-table or composite keys upfront; GSIs for alternate access patterns. No connection pool, pay-per-request billing matches spiky Lambda traffic.

## Read replicas and timeouts

Route analytics Lambdas to **reader endpoints** so OLTP connections stay isolated. Set aggressive **`connect_timeout`** (2–5s) so failing AZs fail fast rather than holding Proxy slots.

```sql
ALTER ROLE app SET statement_timeout = '5s';
ALTER ROLE app SET idle_in_transaction_session_timeout = '10s';
```

## Secrets and rotation

Fetch secrets from Secrets Manager with **extension caching** in the Lambda layer to avoid API throttling on cold starts. For dual-user rotation, Proxy supports two credentials during cutover.

Never run **schema migrations** inside the invocation path — run from CI with a dedicated migration role, not the Lambda app role.

## Anti-patterns

- Opening a new connection inside a loop over SQS records (100 records → 100 connections on one instance before reuse kicks in).
- Using ORM session scope spanning entire API Gateway timeout with open transaction.
- Sharing one global Sequelize pool configured for `max: 100` per Lambda instance.
- Disabling Proxy to "reduce latency" without measuring — handshake savings rarely beat outage cost.

## Observability checklist

- Alert when `DatabaseConnections` > 80% of max for 5 minutes.
- Track Proxy **QueryDatabaseResponseLatency** p99.
- Log `too many connections` and **`remaining connection slots are reserved`** at ERROR with function name dimension.
- Load test at 2× expected peak concurrency before Black Friday.

Serverless database access is a solved problem with boring components: pool at the edge, reuse in the container, timeout aggressively, and choose connectionless stores where relational joins are not the core model. Exciting outages happen when teams pretend Lambda behaves like a long-lived app server.""",
)

POSTS["shared-data-layer-room-kmp"] = (
    {
        "title": "A Shared Data Layer with Room and Kotlin Multiplatform",
        "description": "Build a shared offline data layer with Room on Kotlin Multiplatform: KMP setup, expect/actual database builders, migrations, and sharing DAOs across Android and iOS.",
        "datePublished": "2026-04-13",
        "tags": ["Kotlin Multiplatform", "Room", "Android", "iOS"],
        "keywords": "Room KMP, Room Multiplatform, shared data layer, KMP database, offline storage, SQLite, expect actual",
        "faq": [
            {
                "q": "Does Room support Kotlin Multiplatform?",
                "a": "Yes. Room added Kotlin Multiplatform support so a single Room database definition — entities, DAOs, and the database class — can run on Android, iOS, and JVM. It uses the SQLite driver abstraction under the hood, with a platform-specific driver on each target.",
            },
            {
                "q": "How do you create a Room database in a KMP shared module?",
                "a": "Define the entities, DAOs, and RoomDatabase in commonMain, then provide a platform-specific database builder via expect/actual — Android supplies a Context, iOS supplies a documents-directory path. Both hand the builder a BundledSQLiteDriver so behavior is consistent.",
            },
            {
                "q": "Should I share the whole data layer or just the database?",
                "a": "Share the database, DAOs, and repository logic in commonMain, and keep platform-specific concerns — file paths, keychain access, background scheduling — behind expect/actual or dependency injection. The repository API stays common; the wiring is per-platform.",
            },
        ],
    },
    r"""We shipped Android offline-first in six months. iOS was "next quarter" until the product team counted duplicate bug fixes across two SQLite wrappers. Room on Kotlin Multiplatform let us move entities, DAOs, and repository logic into `commonMain` while keeping platform wiring thin. One migration path, one source of truth for cache invalidation, two app stores. The hard part was not Room syntax — it was drawing boundaries so iOS background refresh and Android WorkManager did not leak into shared code.

## Module layout

Typical KMP structure for a shared data layer:

```
shared/
  commonMain/kotlin/
    data/local/Entity.kt, Dao.kt, AppDatabase.kt
    data/repository/ItemRepository.kt
  androidMain/kotlin/
    data/local/DatabaseBuilder.android.kt
  iosMain/kotlin/
    data/local/DatabaseBuilder.ios.kt
```

Gradle dependencies (conceptual):

```kotlin
// shared/build.gradle.kts
kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation(libs.room.runtime)
            implementation(libs.sqlite.bundled)
            implementation(libs.kotlinx.coroutines.core)
        }
        androidMain.dependencies {
            implementation(libs.room.runtime) // Android artifact
        }
        iosMain.dependencies {
            implementation(libs.room.runtime) // native driver
        }
    }
}
```

Use the **BundledSQLiteDriver** in common code so Android and iOS share SQLite version behavior — fewer "works on emulator, fails on device" surprises.

## Entities and DAOs in commonMain

```kotlin
@Entity(tableName = "items")
data class ItemEntity(
    @PrimaryKey val id: String,
    val title: String,
    val updatedAt: Long,
    val synced: Boolean = false,
)

@Dao
interface ItemDao {
    @Query("SELECT * FROM items ORDER BY updatedAt DESC")
    fun observeAll(): Flow<List<ItemEntity>>

    @Upsert
    suspend fun upsert(item: ItemEntity)

    @Query("DELETE FROM items WHERE id = :id")
    suspend fun deleteById(id: String)
}
```

```kotlin
@Database(entities = [ItemEntity::class], version = 2)
abstract class AppDatabase : RoomDatabase() {
    abstract fun itemDao(): ItemDao
}
```

Keep entities **dumb storage** — no UI formatting, no platform types. Map to domain models in the repository.

## expect/actual database builder

```kotlin
// commonMain
expect class DatabaseFactory {
    fun create(): AppDatabase
}

// androidMain
actual class DatabaseFactory(private val context: Context) {
    actual fun create(): AppDatabase {
        return Room.databaseBuilder(context, AppDatabase::class.java, "app.db")
            .setDriver(BundledSQLiteDriver())
            .addMigrations(MIGRATION_1_2)
            .build()
    }
}

// iosMain
actual class DatabaseFactory {
    actual fun create(): AppDatabase {
        val dbPath = documentDirectory() + "/app.db"
        return Room.databaseBuilder<AppDatabase>(name = dbPath)
            .setDriver(BundledSQLiteDriver())
            .addMigrations(MIGRATION_1_2)
            .build()
    }
}
```

iOS `documentDirectory()` comes from platform Foundation APIs wrapped in a small actual helper — keep path logic out of repositories.

## Repository pattern in shared code

```kotlin
class ItemRepository(private val dao: ItemDao, private val api: ItemApi) {
    fun observeItems(): Flow<List<Item>> =
        dao.observeAll().map { list -> list.map { it.toDomain() } }

    suspend fun refresh() {
        val remote = api.fetchItems()
        dao.upsertAll(remote.map { it.toEntity(synced = true) })
    }

    suspend fun saveLocal(item: Item) {
        dao.upsert(item.toEntity(synced = false))
    }
}
```

Network calls belong behind an interface (`ItemApi`) with Ktor client in commonMain or expect/actual if certificates differ. **Do not** import Android `Context` into repositories.

## Migrations

Define migrations once in commonMain:

```kotlin
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(connection: SQLiteConnection) {
        connection.execSQL("ALTER TABLE items ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
    }
}
```

Test migrations on both targets in CI — Android instrumented tests and iOS simulator tests reading the same migration chain. Export schema JSON for Room verification:

```kotlin
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}
```

## Sync and conflict handling

Offline-first shared layers need explicit sync policy:

| Strategy | When to use |
|----------|-------------|
| Last-write-wins on `updatedAt` | Simple catalogs |
| Server authoritative | Financial or inventory data |
| CRDT / operational transform | Collaborative editing |

Store **`synced` flag** and queue outbound changes in a `pending_ops` table. Platform schedulers (WorkManager, BGTaskScheduler) trigger `repository.pushPending()` — schedulers stay platform-specific; queue logic stays common.

## Testing

Use **in-memory Room** in `commonTest`:

```kotlin
fun createInMemoryDb(): AppDatabase {
    return Room.inMemoryDatabaseBuilder<AppDatabase>()
        .setDriver(BundledSQLiteDriver())
        .build()
}

@Test
fun upsertAndObserve() = runTest {
    val db = createInMemoryDb()
    val repo = ItemRepository(db.itemDao(), FakeApi())
    repo.saveLocal(Item("1", "Hello"))
    assertEquals(1, repo.observeItems().first().size)
}
```

## Pitfalls

- Putting `@Serializable` network DTOs and Room entities in one class — separation prevents API changes breaking DB schema.
- Running blocking DAO calls on main thread — use coroutines and `Flow` consistently.
- iOS database file in tmp directory — use Documents, not Caches, for persistence.
- Forgetting WAL mode implications on iOS low-memory kills — keep transactions short.

Room KMP turns the shared data layer from a slide-deck promise into compile-once persistence. Invest in repository boundaries and migration tests; the platform-specific surface shrinks to factory builders and background job glue.""",
)

POSTS["supply-chain-dependency-pinning"] = (
    {
        "title": "Pinning Dependencies for Supply-Chain Safety",
        "description": "Unpinned dependencies let typosquatting, compromised releases, and silent breaking changes into your build. Learn lockfiles, hash verification, and pinning strategies that protect your supply chain.",
        "datePublished": "2025-09-28",
        "tags": ["Security", "Supply Chain", "DevOps", "Dependencies"],
        "keywords": "dependency pinning, lockfile security, npm ci, pip hash verification, supply chain attack, typosquatting prevention, reproducible builds",
        "faq": [
            {
                "q": "What is the difference between a lockfile and pinning in package.json?",
                "a": "Semver ranges in package.json (like ^1.2.3) allow any compatible version on the next install. A lockfile (package-lock.json, yarn.lock, poetry.lock, Cargo.lock) records the exact resolved versions and often integrity hashes of every transitive dependency. Pinning means committing lockfiles and installing from them — npm ci, not npm install — so every build and every developer gets identical dependency trees.",
            },
            {
                "q": "Should I pin direct dependencies to exact versions?",
                "a": "Use lockfiles for exact resolution and keep semver ranges in manifest files for readability — this is the standard approach for npm, pip with requirements.txt + lock, and Cargo. For security-critical or frequently targeted packages (crypto libraries, auth SDKs), pin exact versions in the manifest too. The goal is that no dependency changes without a deliberate, reviewed lockfile update.",
            },
            {
                "q": "How do I safely update pinned dependencies?",
                "a": "Use automated tools (Dependabot, Renovate) that open PRs with lockfile changes, run your CI suite, and include changelogs. Review updates for major version bumps manually. Never run npm update or pip install --upgrade in production pipelines without a PR review. Schedule regular update windows — weekly for patch, monthly for minor — rather than letting dependencies drift for years.",
            },
        ],
    },
    r"""CI passed on Tuesday. On Wednesday, a patch release of a transitive logging helper shipped malware that phoned home from build containers. The diff was not in our `package.json` — it was three levels deep, unlocked because a developer ran `npm install` locally and committed nothing while Jenkins ran `npm install` fresh each night. Pinning is not pedantry about semver; it is the difference between reproducing Tuesday's build and inviting Wednesday's incident.

## Threat model

Supply-chain attacks target dependency resolution:

| Attack | Mechanism | Pinning mitigates |
|--------|-----------|-------------------|
| Typosquatting | `lodash` vs `l0dash` | Review + lock + private registry |
| Account takeover | Maintainer npm publish | Hash lock + delay + provenance |
| Dependency confusion | Internal package name on public registry | Scope + registry config |
| Transitive drift | Unpinned install resolves new patch | Lockfile + ci install |

Reproducible builds mean the same inputs produce the same artifact bit-for-bit (or close enough for container images). Unpinned installs are nondeterministic inputs.

## Lockfiles per ecosystem

**npm / yarn / pnpm**

```json
// package.json — ranges for humans
"dependencies": {
  "express": "^4.19.0"
}
```

Commit `package-lock.json`. CI installs with:

```bash
npm ci --ignore-scripts   # optional: disable lifecycle scripts in CI
```

`npm ci` fails if lock and manifest disagree — catching accidental drift.

**Python (pip-tools / Poetry / uv)**

```bash
pip-compile requirements.in -o requirements.txt --generate-hashes
pip install --require-hashes -r requirements.txt
```

Hashes prevent tarball substitution on the index mirror.

**Go**

```go
// go.mod sums in go.sum — commit both
go build ./...
```

**Rust**

`Cargo.lock` committed for applications; libraries may omit but apps must not.

## Pinning strategies

1. **Lockfile-only pinning (default)** — ranges in manifest, exact tree in lock. Update via PR.
2. **Exact manifest pinning** — `"express": "4.19.2"` for critical deps without caret.
3. **Vendor / mirror** — Artifactory, Verdaccio, npm Enterprise cache with immutability.
4. **SBOM export** — CycloneDX from CI for incident response ("are we affected?").

```yaml
# GitHub Actions excerpt
- run: npm ci
- run: npx @cyclonedx/cyclonedx-npm --output-file sbom.json
- uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.json
```

## Renovate and Dependabot done right

Automate PRs, not blind merges:

```json
// renovate.json
{
  "extends": ["config:recommended"],
  "schedule": ["before 6am on Monday"],
  "packageRules": [
    {
      "matchUpdateTypes": ["patch"],
      "automerge": true,
      "automergeType": "pr"
    },
    {
      "matchPackagePatterns": ["^@company/"],
      "registryUrls": ["https://npm.internal.example.com"]
    }
  ]
}
```

Require CI green and codeowner review for major bumps. Group patch updates weekly to avoid alert fatigue.

## npm lifecycle scripts and install hooks

Malware often runs in `postinstall`. Mitigations:

- `npm ci --ignore-scripts` in CI, then explicit allowlist for packages that need build steps.
- `.npmrc`: `ignore-scripts=true` globally in CI images.
- Review new dependencies for install scripts before merging.

## Internal registry configuration

```ini
# .npmrc
@myorg:registry=https://npm.internal.example.com/
save-exact=true
engine-strict=true
```

Prevent **dependency confusion** by reserving internal package names on public registries and blocking public installs of `@myorg/*` scopes in CI policy.

## Verification and provenance

- Enable **npm audit** / **`cargo audit`** / **OSV-Scanner** in CI as signal, not gate alone.
- Sigstore **cosign** for internal packages you publish.
- SLSA build provenance attestation on release artifacts.

When CVE hits, pinned SBOM answers "who runs log4j 2.14.1?" in minutes instead of archaeology.

## Organizational policy

Document:

- Lockfiles are mandatory; PRs that delete lockfile lines without explanation are blocked.
- Production deploys never run bare `npm install`.
- Emergency override requires security + platform approval.
- Quarterly dependency hygiene sprint — not once-a-decade React upgrade trauma.

## Common failures

- `.gitignore` excluding lockfiles "because merge conflicts."
- Docker `RUN npm install` instead of `npm ci` — layer cache hides drift until cache bust.
- Monorepo with one lock per package vs shared — pick one model consistently.
- Pinning direct deps but ignoring transitive updates in lock review.

Pinning dependencies trades spontaneous patch freshness for control. That trade is correct for production systems. The goal is not zero updates — it is **every update is intentional, reviewable, and reversible**.""",
)

POSTS["technical-writing-for-engineers"] = (
    {
        "title": "Technical Writing for Engineers",
        "description": "How engineers write documentation that gets read: audience-first structure, runnable examples, diagrams, review workflows, and maintaining docs as code.",
        "datePublished": "2025-12-02",
        "tags": ["Career", "Documentation", "Communication", "Engineering"],
        "keywords": "technical writing engineers, documentation best practices, README structure, docs as code, engineering communication, runbook writing",
        "faq": [
            {
                "q": "What makes technical documentation useful vs ignored?",
                "a": "Useful docs answer a specific question for a specific reader in under two minutes. They lead with the outcome (how to deploy, how to debug X), include copy-pasteable commands that work, and stay current with the code. Ignored docs are vague encyclopedias, missing prerequisites, or obviously stale — wrong version numbers, broken links, references to removed services.",
            },
            {
                "q": "How should engineers structure a README?",
                "a": "Open with one sentence on what the project does and who it is for. Follow with quickstart (install + run in five steps), prerequisites, configuration table, common tasks, troubleshooting FAQ, and links to deeper docs. Put architecture and contribution guidelines after the reader can successfully run something.",
            },
            {
                "q": "Should documentation live in the same repo as code?",
                "a": "Yes for anything tied to implementation — API docs, runbooks, ADRs, and READMEs should version with code in the same repo or monorepo docs folder. Use docs-as-code workflows: Markdown in git, PR review for doc changes, CI link checking, and deploy docs from the same pipeline that ships the service.",
            },
        ],
    },
    r"""The onboarding doc said `docker-compose up` — no mention that SSO credentials take fifteen minutes to propagate or that the seed script requires VPN. New hires stopped reading internal docs entirely and DM'd seniors instead. That is not a literacy problem; it is a writing problem. Technical writing for engineers is not about prettier prose. It is about reducing the distance between a question and a verified answer.

## Audience first

Every doc needs a labeled audience in the first screen:

- **New developer** — clone to running test in 30 minutes
- **On-call engineer** — symptom → mitigation in 3 AM cognitive state
- **Integrator** — API auth, rate limits, error codes
- **Future you** — why we chose Postgres over Dynamo for billing

If you mix audiences in one page, everyone loses. Split runbooks from architecture deep dives.

## README structure that works

```markdown
# payments-service

Processes card charges and emits ledger events. Owns PCI scope boundary B.

## Quickstart
1. `cp .env.example .env` and fill STRIPE_KEY from 1Password vault Payments.
2. `docker compose up -d postgres`
3. `npm ci && npm run migrate && npm run dev`
4. Verify: `curl localhost:3000/health` → `{"ok":true}`

## Configuration
| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | yes | Postgres connection string |
| STRIPE_KEY | yes | Test key for dev |

## Common tasks
- Run migrations: `npm run migrate`
- Trigger replay: see [runbooks/replay.md](./runbooks/replay.md)

## Troubleshooting
**Error: connection refused on 5432** — Docker not running or wrong DATABASE_URL port.
```

Lead with outcomes, not history. "Founded in 2019 as a monolith extract" belongs in an ADR, not quickstart.

## Runnable examples

Untested commands rot. CI should execute doc snippets where feasible:

```yaml
# .github/workflows/docs-check.yml
- name: Verify quickstart commands
  run: |
    ./scripts/doc-smoke-test.sh
```

At minimum, re-run quickstart steps on every major release. Timestamp the last verified date at the top: `Last verified: 2026-07-10 on macOS 14 / Node 20`.

Code blocks need context — language, working directory, expected output:

```bash
# From repo root — expect "2 passed"
npm test -- --grep "checkout"
```

## Diagrams when relationships matter

ASCII and Mermaid beat prose for flows:

```
Client → API Gateway → payments-service → Postgres
                              │
                              └── Kafka → ledger-projector
```

One diagram per doc maximum for onboarding; link to architecture collection for the full map.

## Runbook writing for incidents

Format: **Symptom → Impact → Diagnosis → Mitigation → Escalation**

```markdown
## Symptom: elevated 502 on /charge

**Impact:** Checkout failure; revenue loss.

**Check:**
1. `kubectl get pods -n payments` — CrashLoopBackOff?
2. Grafana dashboard Payments Overview — DB latency spike?

**Mitigate:**
- Scale deployments: `kubectl scale deploy/payments --replicas=10`
- If DB: enable read-only mode via `/admin/readonly` (requires break-glass)

**Escalate:** #payments-oncall, page if error rate > 5% for 10m.
```

Avoid narrative war stories in runbooks — link postmortem separately.

## Docs as code

- Markdown in git beside the service
- PR review required for doc changes affecting public APIs
- **markdown-link-check** in CI
- Version docs with releases (`/docs/v2/` or tags)

Architecture Decision Records (ADRs) capture **why**:

```markdown
# ADR 0042: Use idempotency keys for charge API

## Status: accepted
## Context
Network retries duplicate charges without idempotency.
## Decision
Require Idempotency-Key header on POST /charge.
## Consequences
Clients must generate UUIDs; 24h key retention in Redis.
```

## Review workflow

Treat doc PRs like code PRs:

1. Author assigns reviewer who did not write the feature (fresh eyes).
2. Reviewer follows quickstart on clean machine or codespace.
3. Checklist: audience clear, commands run, links work, secrets not committed.

For external docs, add tech writer or PM review for tone; engineers own accuracy.

## Maintenance habits

- **Definition of Done** includes "updated docs" for user-visible changes.
- Deprecation notices with removal date in docs before code deletes feature.
- Quarterly stale doc sweep — broken links, removed env vars.
- Search analytics on docs site: top queries with no results get new pages.

## Style principles

- Active voice: "Run the migration" not "The migration should be run."
- Short paragraphs; headers every 3–5 paragraphs.
- Define acronyms once.
- Prefer tables for config and error codes.
- Delete redundant docs — two conflicting pages worse than none.

## What to avoid

- Auto-generated API dumps with no narrative (supplement, not substitute).
- Wikis without ownership — "everyone's problem is no one's."
- Pasting Slack threads as permanent docs.
- Writing for impressing peers instead of unlocking the next person.

Good technical writing is a force multiplier: fewer interrupts, faster incidents, safer onboarding. The bar is not literary — it is **someone you will never meet succeeds without pinging you at 4 PM**.""",
)
