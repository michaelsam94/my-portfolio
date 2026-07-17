"""Topic sections batch11 chunk3."""

SECTIONS = {'web-performance-module-preload-import': [('Why this breaks in production',
                                            ['We preloaded the entire ES module graph — forty-two '
                                             'modulepreload tags — and FCP regressed because the browser '
                                             'fetched every lazy route before the entry module finished '
                                             'parsing.',
                                             '**When:** When your entry chunk dynamically imports '
                                             'above-the-fold UI and LCP depends on a nested module',
                                             '**Avoid:** Preloading every dynamic import instead of only '
                                             'modules on the critical path to interactive']),
                                           ('How it works',
                                            ['`modulepreload` fetches and parses ES modules before the '
                                             'importer runs, inserting them into the module map. Unlike '
                                             'script preload, it respects module semantics including CORS '
                                             'and strict mode.',
                                             'Map your bundle with Vite `--metafile` or webpack stats. '
                                             'Preload only modules on the path from entry to LCP and first '
                                             'interaction — not every lazy route chunk.',
                                             'Cap at three to five modulepreload tags. On 4G, each extra '
                                             'preload competes with the hero image for bandwidth. Verify '
                                             'hrefs match post-import-map resolved URLs.',
                                             'In DevTools Network, filter Initiator preload. Compare FCP and '
                                             'LCP p75 with hints on vs off using RUM throttled profiles.']),
                                           ('Implementation',
                                            ['Ship one route or endpoint first with metrics wired before '
                                             'broad rollout.',
                                             'Compare canary p75 to control for a full business day in '
                                             'target regions.',
                                             'Test refresh, back, double-submit, offline, and keyboard-only '
                                             'paths manually.']),
                                           ('Failure modes',
                                            ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                             'and test logged-in states.',
                                             'Third-party scripts change without your deploy — audit '
                                             'quarterly.',
                                             'Global metric averages hide regional or device-class '
                                             'regressions.']),
                                           ('Measurement',
                                            ['Leading: error rate, p75 latency, validation failures. '
                                             'Lagging: tickets, conversion, churn.',
                                             'Slice dashboards by route, device, connection type, release '
                                             'version.',
                                             'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                           ('Ship checklist',
                                            ['Name invariant, owner, leading metric, and rollback path '
                                             'before promote.',
                                             'Link runbook from dashboard — not buried wiki.',
                                             'Quarterly re-verify after browser releases and traffic '
                                             'shifts.'])],
 'web-performance-multi-step-form-wizard': [('Why this breaks in production',
                                             ['Checkout abandonment spiked when we added a five-step wizard '
                                              'without persisting draft state — users who refreshed on step '
                                              'three lost everything and left.',
                                              '**When:** When flows exceed three fields or require '
                                              'verification mid-stream',
                                              '**Avoid:** Storing wizard state only in React memory without '
                                              'URL or server draft persistence']),
                                            ('How it works',
                                             ['Production multi-step form wizards with persisted progress '
                                              'requires explicit invariants, tests, and metrics — not '
                                              'checklist architecture diagrams.',
                                              'Field p75 on mid-tier Android over 4G is the honest '
                                              'acceptance test for multi-step form wizards with persisted '
                                              'progress.',
                                              'Rehearse anti-pattern in design review: Storing wizard state '
                                              'only in React memory without URL or server draft persistence',
                                              'Rollback via feature flag or cache purge must be documented '
                                              'in the PR before merge.']),
                                            ('Implementation',
                                             ['Ship one route or endpoint first with metrics wired before '
                                              'broad rollout.',
                                              'Compare canary p75 to control for a full business day in '
                                              'target regions.',
                                              'Test refresh, back, double-submit, offline, and keyboard-only '
                                              'paths manually.']),
                                            ('Failure modes',
                                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                              'and test logged-in states.',
                                              'Third-party scripts change without your deploy — audit '
                                              'quarterly.',
                                              'Global metric averages hide regional or device-class '
                                              'regressions.']),
                                            ('Measurement',
                                             ['Leading: error rate, p75 latency, validation failures. '
                                              'Lagging: tickets, conversion, churn.',
                                              'Slice dashboards by route, device, connection type, release '
                                              'version.',
                                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                            ('Ship checklist',
                                             ['Name invariant, owner, leading metric, and rollback path '
                                              'before promote.',
                                              'Link runbook from dashboard — not buried wiki.',
                                              'Quarterly re-verify after browser releases and traffic '
                                              'shifts.'])],
 'web-performance-navigation-timing-api': [('Why this breaks in production',
                                            ['Our RUM dashboard showed 200ms TTFB while users complained of '
                                             'slow loads — Navigation Timing revealed 1.8s spent in redirect '
                                             'chains and TLS handshakes the server metric never saw.',
                                             '**When:** When you need field data on redirect, DNS, TLS, and '
                                             'DOM phases beyond server-side TTFB',
                                             '**Avoid:** Reporting only responseStart minus fetchStart '
                                             'without breaking down redirect and TLS time']),
                                           ('How it works',
                                            ['Production Navigation Timing API for Real User Monitoring '
                                             'requires explicit invariants, tests, and metrics — not '
                                             'checklist architecture diagrams.',
                                             'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                             'test for Navigation Timing API for Real User Monitoring.',
                                             'Rehearse anti-pattern in design review: Reporting only '
                                             'responseStart minus fetchStart without breaking down redirect '
                                             'and TLS time',
                                             'Rollback via feature flag or cache purge must be documented in '
                                             'the PR before merge.']),
                                           ('Implementation',
                                            ['Ship one route or endpoint first with metrics wired before '
                                             'broad rollout.',
                                             'Compare canary p75 to control for a full business day in '
                                             'target regions.',
                                             'Test refresh, back, double-submit, offline, and keyboard-only '
                                             'paths manually.']),
                                           ('Failure modes',
                                            ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                             'and test logged-in states.',
                                             'Third-party scripts change without your deploy — audit '
                                             'quarterly.',
                                             'Global metric averages hide regional or device-class '
                                             'regressions.']),
                                           ('Measurement',
                                            ['Leading: error rate, p75 latency, validation failures. '
                                             'Lagging: tickets, conversion, churn.',
                                             'Slice dashboards by route, device, connection type, release '
                                             'version.',
                                             'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                           ('Ship checklist',
                                            ['Name invariant, owner, leading metric, and rollback path '
                                             'before promote.',
                                             'Link runbook from dashboard — not buried wiki.',
                                             'Quarterly re-verify after browser releases and traffic '
                                             'shifts.'])],
 'web-performance-network-status-indicator': [('Why this breaks in production',
                                               ['Users on flaky subway Wi-Fi kept submitting payment forms '
                                                'that timed out — a simple offline banner would have '
                                                'disabled submit and saved forty support tickets a week.',
                                                '**When:** When your app serves mobile users on intermittent '
                                                'connectivity',
                                                '**Avoid:** Showing a toast once on offline without '
                                                'persisting state or disabling mutating actions']),
                                              ('How it works',
                                               ['Production network status indicators and offline-aware UI '
                                                'requires explicit invariants, tests, and metrics — not '
                                                'checklist architecture diagrams.',
                                                'Field p75 on mid-tier Android over 4G is the honest '
                                                'acceptance test for network status indicators and '
                                                'offline-aware UI.',
                                                'Rehearse anti-pattern in design review: Showing a toast '
                                                'once on offline without persisting state or disabling '
                                                'mutating actions',
                                                'Rollback via feature flag or cache purge must be documented '
                                                'in the PR before merge.']),
                                              ('Implementation',
                                               ['Ship one route or endpoint first with metrics wired before '
                                                'broad rollout.',
                                                'Compare canary p75 to control for a full business day in '
                                                'target regions.',
                                                'Test refresh, back, double-submit, offline, and '
                                                'keyboard-only paths manually.']),
                                              ('Failure modes',
                                               ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                'CDN and test logged-in states.',
                                                'Third-party scripts change without your deploy — audit '
                                                'quarterly.',
                                                'Global metric averages hide regional or device-class '
                                                'regressions.']),
                                              ('Measurement',
                                               ['Leading: error rate, p75 latency, validation failures. '
                                                'Lagging: tickets, conversion, churn.',
                                                'Slice dashboards by route, device, connection type, release '
                                                'version.',
                                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                              ('Ship checklist',
                                               ['Name invariant, owner, leading metric, and rollback path '
                                                'before promote.',
                                                'Link runbook from dashboard — not buried wiki.',
                                                'Quarterly re-verify after browser releases and traffic '
                                                'shifts.'])],
 'web-performance-optimistic-navigation-ui': [('Why this breaks in production',
                                               ['Instant route transitions felt great until users clicked '
                                                'back and saw stale data from the optimistic cache — we had '
                                                "no rollback when the prefetch 404'd.",
                                                '**When:** When perceived speed matters for multi-page or '
                                                'SPA navigation patterns',
                                                '**Avoid:** Applying optimistic UI without validating '
                                                'prefetch success or invalidating on failure']),
                                              ('How it works',
                                               ['Production optimistic navigation UI with safe rollback '
                                                'requires explicit invariants, tests, and metrics — not '
                                                'checklist architecture diagrams.',
                                                'Field p75 on mid-tier Android over 4G is the honest '
                                                'acceptance test for optimistic navigation UI with safe '
                                                'rollback.',
                                                'Rehearse anti-pattern in design review: Applying optimistic '
                                                'UI without validating prefetch success or invalidating on '
                                                'failure',
                                                'Rollback via feature flag or cache purge must be documented '
                                                'in the PR before merge.']),
                                              ('Implementation',
                                               ['Ship one route or endpoint first with metrics wired before '
                                                'broad rollout.',
                                                'Compare canary p75 to control for a full business day in '
                                                'target regions.',
                                                'Test refresh, back, double-submit, offline, and '
                                                'keyboard-only paths manually.']),
                                              ('Failure modes',
                                               ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                'CDN and test logged-in states.',
                                                'Third-party scripts change without your deploy — audit '
                                                'quarterly.',
                                                'Global metric averages hide regional or device-class '
                                                'regressions.']),
                                              ('Measurement',
                                               ['Leading: error rate, p75 latency, validation failures. '
                                                'Lagging: tickets, conversion, churn.',
                                                'Slice dashboards by route, device, connection type, release '
                                                'version.',
                                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                              ('Ship checklist',
                                               ['Name invariant, owner, leading metric, and rollback path '
                                                'before promote.',
                                                'Link runbook from dashboard — not buried wiki.',
                                                'Quarterly re-verify after browser releases and traffic '
                                                'shifts.'])],
 'web-performance-passive-event-listeners': [('Why this breaks in production',
                                              ['Scroll jank on mobile product pages traced to a third-party '
                                               'analytics handler calling preventDefault on touchmove — '
                                               'switching to passive listeners fixed INP without removing '
                                               'tracking.',
                                               '**When:** When touch or wheel handlers do not call '
                                               'preventDefault',
                                               '**Avoid:** Adding { passive: true } to listeners that need '
                                               'preventDefault for custom swipe gestures']),
                                             ('How it works',
                                              ['Production passive event listeners for scroll and touch '
                                               'performance requires explicit invariants, tests, and metrics '
                                               '— not checklist architecture diagrams.',
                                               'Field p75 on mid-tier Android over 4G is the honest '
                                               'acceptance test for passive event listeners for scroll and '
                                               'touch performance.',
                                               'Rehearse anti-pattern in design review: Adding { passive: '
                                               'true } to listeners that need preventDefault for custom '
                                               'swipe gestures',
                                               'Rollback via feature flag or cache purge must be documented '
                                               'in the PR before merge.']),
                                             ('Implementation',
                                              ['Ship one route or endpoint first with metrics wired before '
                                               'broad rollout.',
                                               'Compare canary p75 to control for a full business day in '
                                               'target regions.',
                                               'Test refresh, back, double-submit, offline, and '
                                               'keyboard-only paths manually.']),
                                             ('Failure modes',
                                              ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                               'and test logged-in states.',
                                               'Third-party scripts change without your deploy — audit '
                                               'quarterly.',
                                               'Global metric averages hide regional or device-class '
                                               'regressions.']),
                                             ('Measurement',
                                              ['Leading: error rate, p75 latency, validation failures. '
                                               'Lagging: tickets, conversion, churn.',
                                               'Slice dashboards by route, device, connection type, release '
                                               'version.',
                                               'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                             ('Ship checklist',
                                              ['Name invariant, owner, leading metric, and rollback path '
                                               'before promote.',
                                               'Link runbook from dashboard — not buried wiki.',
                                               'Quarterly re-verify after browser releases and traffic '
                                               'shifts.'])],
 'web-performance-password-strength-meter': [('Why this breaks in production',
                                              ['Our zxcvbn meter turned green on Passw0rd! while Have I Been '
                                               'Pwned flagged it in the top ten thousand breached passwords '
                                               '— color alone misled users.',
                                               '**When:** When registration or password-change flows need '
                                               'security without frustrating users',
                                               '**Avoid:** Scoring only on character classes without breach '
                                               'corpus or length-first guidance']),
                                             ('How it works',
                                              ['Production password strength meters with breach-aware '
                                               'feedback requires explicit invariants, tests, and metrics — '
                                               'not checklist architecture diagrams.',
                                               'Field p75 on mid-tier Android over 4G is the honest '
                                               'acceptance test for password strength meters with '
                                               'breach-aware feedback.',
                                               'Rehearse anti-pattern in design review: Scoring only on '
                                               'character classes without breach corpus or length-first '
                                               'guidance',
                                               'Rollback via feature flag or cache purge must be documented '
                                               'in the PR before merge.']),
                                             ('Implementation',
                                              ['Ship one route or endpoint first with metrics wired before '
                                               'broad rollout.',
                                               'Compare canary p75 to control for a full business day in '
                                               'target regions.',
                                               'Test refresh, back, double-submit, offline, and '
                                               'keyboard-only paths manually.']),
                                             ('Failure modes',
                                              ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                               'and test logged-in states.',
                                               'Third-party scripts change without your deploy — audit '
                                               'quarterly.',
                                               'Global metric averages hide regional or device-class '
                                               'regressions.']),
                                             ('Measurement',
                                              ['Leading: error rate, p75 latency, validation failures. '
                                               'Lagging: tickets, conversion, churn.',
                                               'Slice dashboards by route, device, connection type, release '
                                               'version.',
                                               'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                             ('Ship checklist',
                                              ['Name invariant, owner, leading metric, and rollback path '
                                               'before promote.',
                                               'Link runbook from dashboard — not buried wiki.',
                                               'Quarterly re-verify after browser releases and traffic '
                                               'shifts.'])],
 'web-performance-prefetch-on-hover-intent': [('Why this breaks in production',
                                               ['Aggressive prefetch on every mouseenter burned 40% more '
                                                'bandwidth on mobile — hover intent with 150ms delay and '
                                                'viewport checks cut waste without hurting perceived speed.',
                                                '**When:** When next-page navigation is predictable from '
                                                'link hover patterns',
                                                '**Avoid:** Prefetching on mouseenter without delay, mobile '
                                                'exclusion, or Data Saver respect']),
                                              ('How it works',
                                               ['Production prefetch on hover intent with bandwidth '
                                                'guardrails requires explicit invariants, tests, and metrics '
                                                '— not checklist architecture diagrams.',
                                                'Field p75 on mid-tier Android over 4G is the honest '
                                                'acceptance test for prefetch on hover intent with bandwidth '
                                                'guardrails.',
                                                'Rehearse anti-pattern in design review: Prefetching on '
                                                'mouseenter without delay, mobile exclusion, or Data Saver '
                                                'respect',
                                                'Rollback via feature flag or cache purge must be documented '
                                                'in the PR before merge.']),
                                              ('Implementation',
                                               ['Ship one route or endpoint first with metrics wired before '
                                                'broad rollout.',
                                                'Compare canary p75 to control for a full business day in '
                                                'target regions.',
                                                'Test refresh, back, double-submit, offline, and '
                                                'keyboard-only paths manually.']),
                                              ('Failure modes',
                                               ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                'CDN and test logged-in states.',
                                                'Third-party scripts change without your deploy — audit '
                                                'quarterly.',
                                                'Global metric averages hide regional or device-class '
                                                'regressions.']),
                                              ('Measurement',
                                               ['Leading: error rate, p75 latency, validation failures. '
                                                'Lagging: tickets, conversion, churn.',
                                                'Slice dashboards by route, device, connection type, release '
                                                'version.',
                                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                              ('Ship checklist',
                                               ['Name invariant, owner, leading metric, and rollback path '
                                                'before promote.',
                                                'Link runbook from dashboard — not buried wiki.',
                                                'Quarterly re-verify after browser releases and traffic '
                                                'shifts.'])],
 'web-performance-priority-hints-fetch': [('Why this breaks in production',
                                           ['Setting fetchpriority=high on six hero images did nothing for '
                                            'LCP — the browser still picked the wrong one because only the '
                                            'true LCP candidate should get high priority.',
                                            '**When:** When competing preloads and images dilute browser '
                                            'priority heuristics',
                                            '**Avoid:** Marking multiple resources fetchpriority=high on the '
                                            'same page']),
                                          ('How it works',
                                           ['Production fetchpriority and Priority Hints for resource '
                                            'scheduling requires explicit invariants, tests, and metrics — '
                                            'not checklist architecture diagrams.',
                                            'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                            'test for fetchpriority and Priority Hints for resource '
                                            'scheduling.',
                                            'Rehearse anti-pattern in design review: Marking multiple '
                                            'resources fetchpriority=high on the same page',
                                            'Rollback via feature flag or cache purge must be documented in '
                                            'the PR before merge.']),
                                          ('Implementation',
                                           ['Ship one route or endpoint first with metrics wired before '
                                            'broad rollout.',
                                            'Compare canary p75 to control for a full business day in target '
                                            'regions.',
                                            'Test refresh, back, double-submit, offline, and keyboard-only '
                                            'paths manually.']),
                                          ('Failure modes',
                                           ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                            'and test logged-in states.',
                                            'Third-party scripts change without your deploy — audit '
                                            'quarterly.',
                                            'Global metric averages hide regional or device-class '
                                            'regressions.']),
                                          ('Measurement',
                                           ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                            'tickets, conversion, churn.',
                                            'Slice dashboards by route, device, connection type, release '
                                            'version.',
                                            'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                          ('Ship checklist',
                                           ['Name invariant, owner, leading metric, and rollback path before '
                                            'promote.',
                                            'Link runbook from dashboard — not buried wiki.',
                                            'Quarterly re-verify after browser releases and traffic '
                                            'shifts.'])],
 'web-performance-progressive-enhancement-modern': [('Why this breaks in production',
                                                     ['The marketing team shipped a React-only contact form '
                                                      '— when JS failed on a corporate proxy, leads dropped '
                                                      'to zero until we added a native form action fallback.',
                                                      '**When:** When reliability and accessibility matter '
                                                      'more than cutting-edge-only APIs',
                                                      '**Avoid:** Assuming evergreen browsers means '
                                                      'JavaScript is always available']),
                                                    ('How it works',
                                                     ['Production progressive enhancement with modern '
                                                      'baseline browsers requires explicit invariants, '
                                                      'tests, and metrics — not checklist architecture '
                                                      'diagrams.',
                                                      'Field p75 on mid-tier Android over 4G is the honest '
                                                      'acceptance test for progressive enhancement with '
                                                      'modern baseline browsers.',
                                                      'Rehearse anti-pattern in design review: Assuming '
                                                      'evergreen browsers means JavaScript is always '
                                                      'available',
                                                      'Rollback via feature flag or cache purge must be '
                                                      'documented in the PR before merge.']),
                                                    ('Implementation',
                                                     ['Ship one route or endpoint first with metrics wired '
                                                      'before broad rollout.',
                                                      'Compare canary p75 to control for a full business day '
                                                      'in target regions.',
                                                      'Test refresh, back, double-submit, offline, and '
                                                      'keyboard-only paths manually.']),
                                                    ('Failure modes',
                                                     ['Staging on office Wi-Fi with empty cache misleads — '
                                                      'warm CDN and test logged-in states.',
                                                      'Third-party scripts change without your deploy — '
                                                      'audit quarterly.',
                                                      'Global metric averages hide regional or device-class '
                                                      'regressions.']),
                                                    ('Measurement',
                                                     ['Leading: error rate, p75 latency, validation '
                                                      'failures. Lagging: tickets, conversion, churn.',
                                                      'Slice dashboards by route, device, connection type, '
                                                      'release version.',
                                                      'Alert week-over-week p75 regression on tier-1 '
                                                      'surfaces.']),
                                                    ('Ship checklist',
                                                     ['Name invariant, owner, leading metric, and rollback '
                                                      'path before promote.',
                                                      'Link runbook from dashboard — not buried wiki.',
                                                      'Quarterly re-verify after browser releases and '
                                                      'traffic shifts.'])],
 'web-performance-rate-limit-user-feedback': [('Why this breaks in production',
                                               ['429 responses returned JSON errors our UI never surfaced — '
                                                'users hammered submit thinking the button was broken, '
                                                'tripling rate-limit hits during the launch spike.',
                                                '**When:** When public APIs or forms enforce per-IP or '
                                                'per-user throttling',
                                                '**Avoid:** Returning bare 429 without Retry-After, human '
                                                'copy, or disabled submit state']),
                                              ('How it works',
                                               ['Production rate-limit feedback UX with Retry-After headers '
                                                'requires explicit invariants, tests, and metrics — not '
                                                'checklist architecture diagrams.',
                                                'Field p75 on mid-tier Android over 4G is the honest '
                                                'acceptance test for rate-limit feedback UX with Retry-After '
                                                'headers.',
                                                'Rehearse anti-pattern in design review: Returning bare 429 '
                                                'without Retry-After, human copy, or disabled submit state',
                                                'Rollback via feature flag or cache purge must be documented '
                                                'in the PR before merge.']),
                                              ('Implementation',
                                               ['Ship one route or endpoint first with metrics wired before '
                                                'broad rollout.',
                                                'Compare canary p75 to control for a full business day in '
                                                'target regions.',
                                                'Test refresh, back, double-submit, offline, and '
                                                'keyboard-only paths manually.']),
                                              ('Failure modes',
                                               ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                'CDN and test logged-in states.',
                                                'Third-party scripts change without your deploy — audit '
                                                'quarterly.',
                                                'Global metric averages hide regional or device-class '
                                                'regressions.']),
                                              ('Measurement',
                                               ['Leading: error rate, p75 latency, validation failures. '
                                                'Lagging: tickets, conversion, churn.',
                                                'Slice dashboards by route, device, connection type, release '
                                                'version.',
                                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                              ('Ship checklist',
                                               ['Name invariant, owner, leading metric, and rollback path '
                                                'before promote.',
                                                'Link runbook from dashboard — not buried wiki.',
                                                'Quarterly re-verify after browser releases and traffic '
                                                'shifts.'])],
 'web-performance-requestidlecallback-patterns': [('Why this breaks in production',
                                                   ['Analytics batching in requestIdleCallback never ran on '
                                                    'busy checkout pages — users navigated away before idle '
                                                    'fired and we lost conversion events.',
                                                    '**When:** When deferring analytics, prefetch, or '
                                                    'non-urgent DOM work off the critical path',
                                                    '**Avoid:** Assuming requestIdleCallback always fires — '
                                                    'it does not under sustained main-thread load']),
                                                  ('How it works',
                                                   ['Production requestIdleCallback for non-critical '
                                                    'deferred work requires explicit invariants, tests, and '
                                                    'metrics — not checklist architecture diagrams.',
                                                    'Field p75 on mid-tier Android over 4G is the honest '
                                                    'acceptance test for requestIdleCallback for '
                                                    'non-critical deferred work.',
                                                    'Rehearse anti-pattern in design review: Assuming '
                                                    'requestIdleCallback always fires — it does not under '
                                                    'sustained main-thread load',
                                                    'Rollback via feature flag or cache purge must be '
                                                    'documented in the PR before merge.']),
                                                  ('Implementation',
                                                   ['Ship one route or endpoint first with metrics wired '
                                                    'before broad rollout.',
                                                    'Compare canary p75 to control for a full business day '
                                                    'in target regions.',
                                                    'Test refresh, back, double-submit, offline, and '
                                                    'keyboard-only paths manually.']),
                                                  ('Failure modes',
                                                   ['Staging on office Wi-Fi with empty cache misleads — '
                                                    'warm CDN and test logged-in states.',
                                                    'Third-party scripts change without your deploy — audit '
                                                    'quarterly.',
                                                    'Global metric averages hide regional or device-class '
                                                    'regressions.']),
                                                  ('Measurement',
                                                   ['Leading: error rate, p75 latency, validation failures. '
                                                    'Lagging: tickets, conversion, churn.',
                                                    'Slice dashboards by route, device, connection type, '
                                                    'release version.',
                                                    'Alert week-over-week p75 regression on tier-1 '
                                                    'surfaces.']),
                                                  ('Ship checklist',
                                                   ['Name invariant, owner, leading metric, and rollback '
                                                    'path before promote.',
                                                    'Link runbook from dashboard — not buried wiki.',
                                                    'Quarterly re-verify after browser releases and traffic '
                                                    'shifts.'])],
 'web-performance-resize-observer-layout': [('Why this breaks in production',
                                             ['A ResizeObserver loop updating chart dimensions on every '
                                              "pixel change triggered 'ResizeObserver loop limit exceeded' "
                                              'and froze dashboards for ten seconds.',
                                              '**When:** When components react to container size changes — '
                                              'charts, sticky sidebars, responsive typography',
                                              '**Avoid:** Reading layout properties in ResizeObserver '
                                              'callback then synchronously writing DOM — causing loop '
                                              'errors']),
                                            ('How it works',
                                             ['Production ResizeObserver without layout thrashing requires '
                                              'explicit invariants, tests, and metrics — not checklist '
                                              'architecture diagrams.',
                                              'Field p75 on mid-tier Android over 4G is the honest '
                                              'acceptance test for ResizeObserver without layout thrashing.',
                                              'Rehearse anti-pattern in design review: Reading layout '
                                              'properties in ResizeObserver callback then synchronously '
                                              'writing DOM — causing loop errors',
                                              'Rollback via feature flag or cache purge must be documented '
                                              'in the PR before merge.']),
                                            ('Implementation',
                                             ['Ship one route or endpoint first with metrics wired before '
                                              'broad rollout.',
                                              'Compare canary p75 to control for a full business day in '
                                              'target regions.',
                                              'Test refresh, back, double-submit, offline, and keyboard-only '
                                              'paths manually.']),
                                            ('Failure modes',
                                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                              'and test logged-in states.',
                                              'Third-party scripts change without your deploy — audit '
                                              'quarterly.',
                                              'Global metric averages hide regional or device-class '
                                              'regressions.']),
                                            ('Measurement',
                                             ['Leading: error rate, p75 latency, validation failures. '
                                              'Lagging: tickets, conversion, churn.',
                                              'Slice dashboards by route, device, connection type, release '
                                              'version.',
                                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                            ('Ship checklist',
                                             ['Name invariant, owner, leading metric, and rollback path '
                                              'before promote.',
                                              'Link runbook from dashboard — not buried wiki.',
                                              'Quarterly re-verify after browser releases and traffic '
                                              'shifts.'])],
 'web-performance-resource-hints': [('Why this breaks in production',
                                     ['We added preload for every script and stylesheet — twelve preload '
                                      'tags in the head. LCP got worse because the browser prioritized all '
                                      'twelve equally, starving the hero image.',
                                      '**When:** When critical resources compete for connection and '
                                      'bandwidth on first load',
                                      '**Avoid:** Preloading everything instead of two or three truly '
                                      'critical resources']),
                                    ('How it works',
                                     ['Preload is high priority for current page; prefetch is low for likely '
                                      'next navigation. Preconnect warms DNS+TCP+TLS.',
                                      'Limit preload to two or three critical resources — LCP image, primary '
                                      'font, critical CSS. Over-preload starves LCP.',
                                      'Font preload requires crossorigin. Pair LCP image with '
                                      'fetchpriority=high — only one or two high-priority resources per '
                                      'page.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-performance-resumability-qwik': [('Why this breaks in production',
                                        ['Our React island hydrated 400KB on a marketing page that needed '
                                         'one interactive newsletter form — resumability sent 4KB of '
                                         'listener metadata instead of re-executing the whole tree.',
                                         '**When:** When static pages need minimal interactivity without '
                                         'shipping full framework runtime upfront',
                                         '**Avoid:** Choosing resumability for highly dynamic apps where '
                                         'serialization overhead exceeds hydration savings']),
                                       ('How it works',
                                        ['Production Qwik resumability vs traditional hydration requires '
                                         'explicit invariants, tests, and metrics — not checklist '
                                         'architecture diagrams.',
                                         'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                         'test for Qwik resumability vs traditional hydration.',
                                         'Rehearse anti-pattern in design review: Choosing resumability for '
                                         'highly dynamic apps where serialization overhead exceeds hydration '
                                         'savings',
                                         'Rollback via feature flag or cache purge must be documented in the '
                                         'PR before merge.']),
                                       ('Implementation',
                                        ['Ship one route or endpoint first with metrics wired before broad '
                                         'rollout.',
                                         'Compare canary p75 to control for a full business day in target '
                                         'regions.',
                                         'Test refresh, back, double-submit, offline, and keyboard-only '
                                         'paths manually.']),
                                       ('Failure modes',
                                        ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                         'test logged-in states.',
                                         'Third-party scripts change without your deploy — audit quarterly.',
                                         'Global metric averages hide regional or device-class '
                                         'regressions.']),
                                       ('Measurement',
                                        ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                         'tickets, conversion, churn.',
                                         'Slice dashboards by route, device, connection type, release '
                                         'version.',
                                         'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                       ('Ship checklist',
                                        ['Name invariant, owner, leading metric, and rollback path before '
                                         'promote.',
                                         'Link runbook from dashboard — not buried wiki.',
                                         'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-performance-scheduler-yield-api': [('Why this breaks in production',
                                          ['A 180ms click handler blocked the main thread — splitting with '
                                           'scheduler.yield() dropped INP from 280ms to 95ms without '
                                           'rewriting the algorithm.',
                                           '**When:** When INP regressions trace to synchronous work in '
                                           'event handlers',
                                           '**Avoid:** Yielding inside tight loops without checking user '
                                           'input priority — still missing deadlines']),
                                         ('How it works',
                                          ['Production scheduler.yield() for long task splitting requires '
                                           'explicit invariants, tests, and metrics — not checklist '
                                           'architecture diagrams.',
                                           'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                           'test for scheduler.yield() for long task splitting.',
                                           'Rehearse anti-pattern in design review: Yielding inside tight '
                                           'loops without checking user input priority — still missing '
                                           'deadlines',
                                           'Rollback via feature flag or cache purge must be documented in '
                                           'the PR before merge.']),
                                         ('Implementation',
                                          ['Ship one route or endpoint first with metrics wired before broad '
                                           'rollout.',
                                           'Compare canary p75 to control for a full business day in target '
                                           'regions.',
                                           'Test refresh, back, double-submit, offline, and keyboard-only '
                                           'paths manually.']),
                                         ('Failure modes',
                                          ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                           'test logged-in states.',
                                           'Third-party scripts change without your deploy — audit '
                                           'quarterly.',
                                           'Global metric averages hide regional or device-class '
                                           'regressions.']),
                                         ('Measurement',
                                          ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                           'tickets, conversion, churn.',
                                           'Slice dashboards by route, device, connection type, release '
                                           'version.',
                                           'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                         ('Ship checklist',
                                          ['Name invariant, owner, leading metric, and rollback path before '
                                           'promote.',
                                           'Link runbook from dashboard — not buried wiki.',
                                           'Quarterly re-verify after browser releases and traffic '
                                           'shifts.'])],
 'web-performance-search-autocomplete-debounce': [('Why this breaks in production',
                                                   ['Every keystroke fired a search API call — debouncing at '
                                                    '300ms cut requests 85% but users complained results '
                                                    'felt laggy until we added optimistic local filtering on '
                                                    'cached prefixes.',
                                                    '**When:** When typeahead queries hit remote APIs on '
                                                    'every input event',
                                                    '**Avoid:** Debouncing without showing immediate local '
                                                    'results or loading affordance']),
                                                  ('How it works',
                                                   ['Production search autocomplete debouncing with '
                                                    'perceived latency tricks requires explicit invariants, '
                                                    'tests, and metrics — not checklist architecture '
                                                    'diagrams.',
                                                    'Field p75 on mid-tier Android over 4G is the honest '
                                                    'acceptance test for search autocomplete debouncing with '
                                                    'perceived latency tricks.',
                                                    'Rehearse anti-pattern in design review: Debouncing '
                                                    'without showing immediate local results or loading '
                                                    'affordance',
                                                    'Rollback via feature flag or cache purge must be '
                                                    'documented in the PR before merge.']),
                                                  ('Implementation',
                                                   ['Ship one route or endpoint first with metrics wired '
                                                    'before broad rollout.',
                                                    'Compare canary p75 to control for a full business day '
                                                    'in target regions.',
                                                    'Test refresh, back, double-submit, offline, and '
                                                    'keyboard-only paths manually.']),
                                                  ('Failure modes',
                                                   ['Staging on office Wi-Fi with empty cache misleads — '
                                                    'warm CDN and test logged-in states.',
                                                    'Third-party scripts change without your deploy — audit '
                                                    'quarterly.',
                                                    'Global metric averages hide regional or device-class '
                                                    'regressions.']),
                                                  ('Measurement',
                                                   ['Leading: error rate, p75 latency, validation failures. '
                                                    'Lagging: tickets, conversion, churn.',
                                                    'Slice dashboards by route, device, connection type, '
                                                    'release version.',
                                                    'Alert week-over-week p75 regression on tier-1 '
                                                    'surfaces.']),
                                                  ('Ship checklist',
                                                   ['Name invariant, owner, leading metric, and rollback '
                                                    'path before promote.',
                                                    'Link runbook from dashboard — not buried wiki.',
                                                    'Quarterly re-verify after browser releases and traffic '
                                                    'shifts.'])],
 'web-performance-selective-hydration': [('Why this breaks in production',
                                          ['Hydrating the entire page blocked the hero image from painting — '
                                           'selective hydration of the chat widget alone recovered 400ms LCP '
                                           'on our docs site.',
                                           '**When:** When SSR pages mix static content with heavy '
                                           'interactive islands',
                                           '**Avoid:** Hydrating all islands in document order instead of '
                                           'prioritizing visible interactive regions']),
                                         ('How it works',
                                          ['Production selective hydration for above-the-fold priority '
                                           'requires explicit invariants, tests, and metrics — not checklist '
                                           'architecture diagrams.',
                                           'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                           'test for selective hydration for above-the-fold priority.',
                                           'Rehearse anti-pattern in design review: Hydrating all islands in '
                                           'document order instead of prioritizing visible interactive '
                                           'regions',
                                           'Rollback via feature flag or cache purge must be documented in '
                                           'the PR before merge.']),
                                         ('Implementation',
                                          ['Ship one route or endpoint first with metrics wired before broad '
                                           'rollout.',
                                           'Compare canary p75 to control for a full business day in target '
                                           'regions.',
                                           'Test refresh, back, double-submit, offline, and keyboard-only '
                                           'paths manually.']),
                                         ('Failure modes',
                                          ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                           'test logged-in states.',
                                           'Third-party scripts change without your deploy — audit '
                                           'quarterly.',
                                           'Global metric averages hide regional or device-class '
                                           'regressions.']),
                                         ('Measurement',
                                          ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                           'tickets, conversion, churn.',
                                           'Slice dashboards by route, device, connection type, release '
                                           'version.',
                                           'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                         ('Ship checklist',
                                          ['Name invariant, owner, leading metric, and rollback path before '
                                           'promote.',
                                           'Link runbook from dashboard — not buried wiki.',
                                           'Quarterly re-verify after browser releases and traffic '
                                           'shifts.'])],
 'web-performance-service-worker-stale-while-revalidate': [('Why this breaks in production',
                                                            ['Stale-while-revalidate served a week-old '
                                                             'pricing page from cache while sales ran a '
                                                             'promotion — users saw wrong prices until hard '
                                                             'refresh.',
                                                             '**When:** When offline-capable caching must '
                                                             'balance speed with content freshness',
                                                             '**Avoid:** Unbounded SWR without max-age, '
                                                             'version headers, or skipWaiting coordination']),
                                                           ('How it works',
                                                            ['Production service worker '
                                                             'stale-while-revalidate with freshness bounds '
                                                             'requires explicit invariants, tests, and '
                                                             'metrics — not checklist architecture diagrams.',
                                                             'Field p75 on mid-tier Android over 4G is the '
                                                             'honest acceptance test for service worker '
                                                             'stale-while-revalidate with freshness bounds.',
                                                             'Rehearse anti-pattern in design review: '
                                                             'Unbounded SWR without max-age, version '
                                                             'headers, or skipWaiting coordination',
                                                             'Rollback via feature flag or cache purge must '
                                                             'be documented in the PR before merge.']),
                                                           ('Implementation',
                                                            ['Ship one route or endpoint first with metrics '
                                                             'wired before broad rollout.',
                                                             'Compare canary p75 to control for a full '
                                                             'business day in target regions.',
                                                             'Test refresh, back, double-submit, offline, '
                                                             'and keyboard-only paths manually.']),
                                                           ('Failure modes',
                                                            ['Staging on office Wi-Fi with empty cache '
                                                             'misleads — warm CDN and test logged-in states.',
                                                             'Third-party scripts change without your deploy '
                                                             '— audit quarterly.',
                                                             'Global metric averages hide regional or '
                                                             'device-class regressions.']),
                                                           ('Measurement',
                                                            ['Leading: error rate, p75 latency, validation '
                                                             'failures. Lagging: tickets, conversion, churn.',
                                                             'Slice dashboards by route, device, connection '
                                                             'type, release version.',
                                                             'Alert week-over-week p75 regression on tier-1 '
                                                             'surfaces.']),
                                                           ('Ship checklist',
                                                            ['Name invariant, owner, leading metric, and '
                                                             'rollback path before promote.',
                                                             'Link runbook from dashboard — not buried wiki.',
                                                             'Quarterly re-verify after browser releases and '
                                                             'traffic shifts.'])],
 'web-performance-sidebar-collapse-responsive': [('Why this breaks in production',
                                                  ['Collapsing the sidebar with display:none reflowed the '
                                                   'entire dashboard — transform-based collapse kept layout '
                                                   'stable and cut CLS from 0.18 to 0.02.',
                                                   '**When:** When navigation panels toggle on mobile and '
                                                   'tablet breakpoints',
                                                   '**Avoid:** Toggling sidebar with properties that trigger '
                                                   'layout (width, display) instead of transform']),
                                                 ('How it works',
                                                  ['Production responsive sidebar collapse without layout '
                                                   'shift requires explicit invariants, tests, and metrics — '
                                                   'not checklist architecture diagrams.',
                                                   'Field p75 on mid-tier Android over 4G is the honest '
                                                   'acceptance test for responsive sidebar collapse without '
                                                   'layout shift.',
                                                   'Rehearse anti-pattern in design review: Toggling sidebar '
                                                   'with properties that trigger layout (width, display) '
                                                   'instead of transform',
                                                   'Rollback via feature flag or cache purge must be '
                                                   'documented in the PR before merge.']),
                                                 ('Implementation',
                                                  ['Ship one route or endpoint first with metrics wired '
                                                   'before broad rollout.',
                                                   'Compare canary p75 to control for a full business day in '
                                                   'target regions.',
                                                   'Test refresh, back, double-submit, offline, and '
                                                   'keyboard-only paths manually.']),
                                                 ('Failure modes',
                                                  ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                   'CDN and test logged-in states.',
                                                   'Third-party scripts change without your deploy — audit '
                                                   'quarterly.',
                                                   'Global metric averages hide regional or device-class '
                                                   'regressions.']),
                                                 ('Measurement',
                                                  ['Leading: error rate, p75 latency, validation failures. '
                                                   'Lagging: tickets, conversion, churn.',
                                                   'Slice dashboards by route, device, connection type, '
                                                   'release version.',
                                                   'Alert week-over-week p75 regression on tier-1 '
                                                   'surfaces.']),
                                                 ('Ship checklist',
                                                  ['Name invariant, owner, leading metric, and rollback path '
                                                   'before promote.',
                                                   'Link runbook from dashboard — not buried wiki.',
                                                   'Quarterly re-verify after browser releases and traffic '
                                                   'shifts.'])],
 'web-performance-skeleton-screen-design': [('Why this breaks in production',
                                             ['Skeleton screens that shimmer for eight seconds felt slower '
                                              'than a spinner — matching skeleton layout to final content '
                                              'and capping display time improved perceived performance '
                                              'scores.',
                                              '**When:** When loading states exceed 300ms and content '
                                              'structure is predictable',
                                              '**Avoid:** Generic gray rectangles that do not match final '
                                              'layout — causing layout shift when content loads']),
                                            ('How it works',
                                             ['Production skeleton screen design matched to final layout '
                                              'requires explicit invariants, tests, and metrics — not '
                                              'checklist architecture diagrams.',
                                              'Field p75 on mid-tier Android over 4G is the honest '
                                              'acceptance test for skeleton screen design matched to final '
                                              'layout.',
                                              'Rehearse anti-pattern in design review: Generic gray '
                                              'rectangles that do not match final layout — causing layout '
                                              'shift when content loads',
                                              'Rollback via feature flag or cache purge must be documented '
                                              'in the PR before merge.']),
                                            ('Implementation',
                                             ['Ship one route or endpoint first with metrics wired before '
                                              'broad rollout.',
                                              'Compare canary p75 to control for a full business day in '
                                              'target regions.',
                                              'Test refresh, back, double-submit, offline, and keyboard-only '
                                              'paths manually.']),
                                            ('Failure modes',
                                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                              'and test logged-in states.',
                                              'Third-party scripts change without your deploy — audit '
                                              'quarterly.',
                                              'Global metric averages hide regional or device-class '
                                              'regressions.']),
                                            ('Measurement',
                                             ['Leading: error rate, p75 latency, validation failures. '
                                              'Lagging: tickets, conversion, churn.',
                                              'Slice dashboards by route, device, connection type, release '
                                              'version.',
                                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                            ('Ship checklist',
                                             ['Name invariant, owner, leading metric, and rollback path '
                                              'before promote.',
                                              'Link runbook from dashboard — not buried wiki.',
                                              'Quarterly re-verify after browser releases and traffic '
                                              'shifts.'])],
 'web-performance-speculative-prerendering': [('Why this breaks in production',
                                               ['Speculation Rules prerendered the wrong checkout step for '
                                                'logged-out users — cached personalized HTML leaked session '
                                                'state until we scoped rules to anonymous routes only.',
                                                '**When:** When navigation patterns are highly predictable '
                                                'and bandwidth cost is acceptable',
                                                '**Avoid:** Prerendering authenticated routes without '
                                                'matching Vary headers and cache isolation']),
                                              ('How it works',
                                               ['Production Speculation Rules API for prerender and prefetch '
                                                'requires explicit invariants, tests, and metrics — not '
                                                'checklist architecture diagrams.',
                                                'Field p75 on mid-tier Android over 4G is the honest '
                                                'acceptance test for Speculation Rules API for prerender and '
                                                'prefetch.',
                                                'Rehearse anti-pattern in design review: Prerendering '
                                                'authenticated routes without matching Vary headers and '
                                                'cache isolation',
                                                'Rollback via feature flag or cache purge must be documented '
                                                'in the PR before merge.']),
                                              ('Implementation',
                                               ['Ship one route or endpoint first with metrics wired before '
                                                'broad rollout.',
                                                'Compare canary p75 to control for a full business day in '
                                                'target regions.',
                                                'Test refresh, back, double-submit, offline, and '
                                                'keyboard-only paths manually.']),
                                              ('Failure modes',
                                               ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                'CDN and test logged-in states.',
                                                'Third-party scripts change without your deploy — audit '
                                                'quarterly.',
                                                'Global metric averages hide regional or device-class '
                                                'regressions.']),
                                              ('Measurement',
                                               ['Leading: error rate, p75 latency, validation failures. '
                                                'Lagging: tickets, conversion, churn.',
                                                'Slice dashboards by route, device, connection type, release '
                                                'version.',
                                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                              ('Ship checklist',
                                               ['Name invariant, owner, leading metric, and rollback path '
                                                'before promote.',
                                                'Link runbook from dashboard — not buried wiki.',
                                                'Quarterly re-verify after browser releases and traffic '
                                                'shifts.'])],
 'web-performance-stale-ui-patterns': [('Why this breaks in production',
                                        ["Showing last week's dashboard data with a tiny 'stale' badge users "
                                         'ignored caused finance to act on outdated numbers — prominent '
                                         'timestamps and refresh affordances fixed trust.',
                                         '**When:** When cached or SWR data may be minutes old but still '
                                         'useful',
                                         '**Avoid:** Hidden stale state — users assume fresh data when UI '
                                         'looks normal']),
                                       ('How it works',
                                        ['Production stale UI patterns with honest freshness communication '
                                         'requires explicit invariants, tests, and metrics — not checklist '
                                         'architecture diagrams.',
                                         'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                         'test for stale UI patterns with honest freshness communication.',
                                         'Rehearse anti-pattern in design review: Hidden stale state — users '
                                         'assume fresh data when UI looks normal',
                                         'Rollback via feature flag or cache purge must be documented in the '
                                         'PR before merge.']),
                                       ('Implementation',
                                        ['Ship one route or endpoint first with metrics wired before broad '
                                         'rollout.',
                                         'Compare canary p75 to control for a full business day in target '
                                         'regions.',
                                         'Test refresh, back, double-submit, offline, and keyboard-only '
                                         'paths manually.']),
                                       ('Failure modes',
                                        ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                         'test logged-in states.',
                                         'Third-party scripts change without your deploy — audit quarterly.',
                                         'Global metric averages hide regional or device-class '
                                         'regressions.']),
                                       ('Measurement',
                                        ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                         'tickets, conversion, churn.',
                                         'Slice dashboards by route, device, connection type, release '
                                         'version.',
                                         'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                       ('Ship checklist',
                                        ['Name invariant, owner, leading metric, and rollback path before '
                                         'promote.',
                                         'Link runbook from dashboard — not buried wiki.',
                                         'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-performance-status-page-integration': [('Why this breaks in production',
                                              ['Our app showed generic errors during an API outage while the '
                                               "status page said 'operational' — embedding status component "
                                               'feed reduced support volume 60%.',
                                               '**When:** When third-party or platform dependencies cause '
                                               'user-visible failures',
                                               '**Avoid:** Hard-coded error messages without linking to live '
                                               'component status']),
                                             ('How it works',
                                              ['Production status page integration in product UI requires '
                                               'explicit invariants, tests, and metrics — not checklist '
                                               'architecture diagrams.',
                                               'Field p75 on mid-tier Android over 4G is the honest '
                                               'acceptance test for status page integration in product UI.',
                                               'Rehearse anti-pattern in design review: Hard-coded error '
                                               'messages without linking to live component status',
                                               'Rollback via feature flag or cache purge must be documented '
                                               'in the PR before merge.']),
                                             ('Implementation',
                                              ['Ship one route or endpoint first with metrics wired before '
                                               'broad rollout.',
                                               'Compare canary p75 to control for a full business day in '
                                               'target regions.',
                                               'Test refresh, back, double-submit, offline, and '
                                               'keyboard-only paths manually.']),
                                             ('Failure modes',
                                              ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                               'and test logged-in states.',
                                               'Third-party scripts change without your deploy — audit '
                                               'quarterly.',
                                               'Global metric averages hide regional or device-class '
                                               'regressions.']),
                                             ('Measurement',
                                              ['Leading: error rate, p75 latency, validation failures. '
                                               'Lagging: tickets, conversion, churn.',
                                               'Slice dashboards by route, device, connection type, release '
                                               'version.',
                                               'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                             ('Ship checklist',
                                              ['Name invariant, owner, leading metric, and rollback path '
                                               'before promote.',
                                               'Link runbook from dashboard — not buried wiki.',
                                               'Quarterly re-verify after browser releases and traffic '
                                               'shifts.'])],
 'web-performance-tab-navigation-aria': [('Why this breaks in production',
                                          ['Keyboard users could not reach tab panel content — roving '
                                           'tabindex and aria-selected fixes took one day and cleared our '
                                           'accessibility audit finding.',
                                           '**When:** When building custom tab interfaces beyond native '
                                           'details/summary',
                                           '**Avoid:** Using div-onClick tabs without role=tablist, keyboard '
                                           'arrows, or focus management']),
                                         ('How it works',
                                          ['Production ARIA tab navigation with roving tabindex requires '
                                           'explicit invariants, tests, and metrics — not checklist '
                                           'architecture diagrams.',
                                           'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                           'test for ARIA tab navigation with roving tabindex.',
                                           'Rehearse anti-pattern in design review: Using div-onClick tabs '
                                           'without role=tablist, keyboard arrows, or focus management',
                                           'Rollback via feature flag or cache purge must be documented in '
                                           'the PR before merge.']),
                                         ('Implementation',
                                          ['Ship one route or endpoint first with metrics wired before broad '
                                           'rollout.',
                                           'Compare canary p75 to control for a full business day in target '
                                           'regions.',
                                           'Test refresh, back, double-submit, offline, and keyboard-only '
                                           'paths manually.']),
                                         ('Failure modes',
                                          ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                           'test logged-in states.',
                                           'Third-party scripts change without your deploy — audit '
                                           'quarterly.',
                                           'Global metric averages hide regional or device-class '
                                           'regressions.']),
                                         ('Measurement',
                                          ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                           'tickets, conversion, churn.',
                                           'Slice dashboards by route, device, connection type, release '
                                           'version.',
                                           'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                         ('Ship checklist',
                                          ['Name invariant, owner, leading metric, and rollback path before '
                                           'promote.',
                                           'Link runbook from dashboard — not buried wiki.',
                                           'Quarterly re-verify after browser releases and traffic '
                                           'shifts.'])],
 'web-performance-third-party-script-impact': [('Why this breaks in production',
                                                ['One chat widget added 1.2s of main-thread blocking — '
                                                 'deferring third parties until after load and using facade '
                                                 'pattern recovered INP without removing support chat.',
                                                 '**When:** When marketing, analytics, and support tools '
                                                 'compete with product JS',
                                                 '**Avoid:** Loading all third parties synchronously in head '
                                                 'because vendor docs say so']),
                                               ('How it works',
                                                ['Production third-party script impact on Core Web Vitals '
                                                 'requires explicit invariants, tests, and metrics — not '
                                                 'checklist architecture diagrams.',
                                                 'Field p75 on mid-tier Android over 4G is the honest '
                                                 'acceptance test for third-party script impact on Core Web '
                                                 'Vitals.',
                                                 'Rehearse anti-pattern in design review: Loading all third '
                                                 'parties synchronously in head because vendor docs say so',
                                                 'Rollback via feature flag or cache purge must be '
                                                 'documented in the PR before merge.']),
                                               ('Implementation',
                                                ['Ship one route or endpoint first with metrics wired before '
                                                 'broad rollout.',
                                                 'Compare canary p75 to control for a full business day in '
                                                 'target regions.',
                                                 'Test refresh, back, double-submit, offline, and '
                                                 'keyboard-only paths manually.']),
                                               ('Failure modes',
                                                ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                 'CDN and test logged-in states.',
                                                 'Third-party scripts change without your deploy — audit '
                                                 'quarterly.',
                                                 'Global metric averages hide regional or device-class '
                                                 'regressions.']),
                                               ('Measurement',
                                                ['Leading: error rate, p75 latency, validation failures. '
                                                 'Lagging: tickets, conversion, churn.',
                                                 'Slice dashboards by route, device, connection type, '
                                                 'release version.',
                                                 'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                               ('Ship checklist',
                                                ['Name invariant, owner, leading metric, and rollback path '
                                                 'before promote.',
                                                 'Link runbook from dashboard — not buried wiki.',
                                                 'Quarterly re-verify after browser releases and traffic '
                                                 'shifts.'])],
 'web-performance-toast-queue-management': [('Why this breaks in production',
                                             ['Twelve simultaneous error toasts stacked off-screen — users '
                                              "missed the critical payment failure among 'Saved' "
                                              'confirmations. A priority queue with deduplication fixed it.',
                                              '**When:** When multiple async operations emit overlapping '
                                              'user feedback',
                                              '**Avoid:** Unbounded toast spam without priority, grouping, '
                                              'or max visible count']),
                                            ('How it works',
                                             ['Production toast notification queue with priority and '
                                              'deduplication requires explicit invariants, tests, and '
                                              'metrics — not checklist architecture diagrams.',
                                              'Field p75 on mid-tier Android over 4G is the honest '
                                              'acceptance test for toast notification queue with priority '
                                              'and deduplication.',
                                              'Rehearse anti-pattern in design review: Unbounded toast spam '
                                              'without priority, grouping, or max visible count',
                                              'Rollback via feature flag or cache purge must be documented '
                                              'in the PR before merge.']),
                                            ('Implementation',
                                             ['Ship one route or endpoint first with metrics wired before '
                                              'broad rollout.',
                                              'Compare canary p75 to control for a full business day in '
                                              'target regions.',
                                              'Test refresh, back, double-submit, offline, and keyboard-only '
                                              'paths manually.']),
                                            ('Failure modes',
                                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                              'and test logged-in states.',
                                              'Third-party scripts change without your deploy — audit '
                                              'quarterly.',
                                              'Global metric averages hide regional or device-class '
                                              'regressions.']),
                                            ('Measurement',
                                             ['Leading: error rate, p75 latency, validation failures. '
                                              'Lagging: tickets, conversion, churn.',
                                              'Slice dashboards by route, device, connection type, release '
                                              'version.',
                                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                            ('Ship checklist',
                                             ['Name invariant, owner, leading metric, and rollback path '
                                              'before promote.',
                                              'Link runbook from dashboard — not buried wiki.',
                                              'Quarterly re-verify after browser releases and traffic '
                                              'shifts.'])],
 'web-performance-tree-shaking-side-effects': [('Why this breaks in production',
                                                ['Our bundle included all of lodash because one file '
                                                 'imported the package root — sideEffects: false in '
                                                 'package.json and per-module imports dropped 90KB gzip.',
                                                 '**When:** When bundle analysis shows unused exports from '
                                                 'large dependencies',
                                                 '**Avoid:** Importing from package root when deep imports '
                                                 'or babel-plugin-import could tree-shake']),
                                               ('How it works',
                                                ['Production tree shaking and sideEffects field in '
                                                 'package.json requires explicit invariants, tests, and '
                                                 'metrics — not checklist architecture diagrams.',
                                                 'Field p75 on mid-tier Android over 4G is the honest '
                                                 'acceptance test for tree shaking and sideEffects field in '
                                                 'package.json.',
                                                 'Rehearse anti-pattern in design review: Importing from '
                                                 'package root when deep imports or babel-plugin-import '
                                                 'could tree-shake',
                                                 'Rollback via feature flag or cache purge must be '
                                                 'documented in the PR before merge.']),
                                               ('Implementation',
                                                ['Ship one route or endpoint first with metrics wired before '
                                                 'broad rollout.',
                                                 'Compare canary p75 to control for a full business day in '
                                                 'target regions.',
                                                 'Test refresh, back, double-submit, offline, and '
                                                 'keyboard-only paths manually.']),
                                               ('Failure modes',
                                                ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                 'CDN and test logged-in states.',
                                                 'Third-party scripts change without your deploy — audit '
                                                 'quarterly.',
                                                 'Global metric averages hide regional or device-class '
                                                 'regressions.']),
                                               ('Measurement',
                                                ['Leading: error rate, p75 latency, validation failures. '
                                                 'Lagging: tickets, conversion, churn.',
                                                 'Slice dashboards by route, device, connection type, '
                                                 'release version.',
                                                 'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                               ('Ship checklist',
                                                ['Name invariant, owner, leading metric, and rollback path '
                                                 'before promote.',
                                                 'Link runbook from dashboard — not buried wiki.',
                                                 'Quarterly re-verify after browser releases and traffic '
                                                 'shifts.'])],
 'web-performance-web-workers-heavy-compute': [('Why this breaks in production',
                                                ['Parsing 50MB CSV on the main thread froze the UI for '
                                                 'twelve seconds — moving Papa Parse to a Web Worker kept '
                                                 'INP under 100ms during upload.',
                                                 '**When:** When client-side parsing, crypto, or image '
                                                 'processing exceeds 50ms',
                                                 '**Avoid:** Posting large payloads to workers without '
                                                 'Transferable objects — doubling memory']),
                                               ('How it works',
                                                ['Production Web Workers for heavy compute off main thread '
                                                 'requires explicit invariants, tests, and metrics — not '
                                                 'checklist architecture diagrams.',
                                                 'Field p75 on mid-tier Android over 4G is the honest '
                                                 'acceptance test for Web Workers for heavy compute off main '
                                                 'thread.',
                                                 'Rehearse anti-pattern in design review: Posting large '
                                                 'payloads to workers without Transferable objects — '
                                                 'doubling memory',
                                                 'Rollback via feature flag or cache purge must be '
                                                 'documented in the PR before merge.']),
                                               ('Implementation',
                                                ['Ship one route or endpoint first with metrics wired before '
                                                 'broad rollout.',
                                                 'Compare canary p75 to control for a full business day in '
                                                 'target regions.',
                                                 'Test refresh, back, double-submit, offline, and '
                                                 'keyboard-only paths manually.']),
                                               ('Failure modes',
                                                ['Staging on office Wi-Fi with empty cache misleads — warm '
                                                 'CDN and test logged-in states.',
                                                 'Third-party scripts change without your deploy — audit '
                                                 'quarterly.',
                                                 'Global metric averages hide regional or device-class '
                                                 'regressions.']),
                                               ('Measurement',
                                                ['Leading: error rate, p75 latency, validation failures. '
                                                 'Lagging: tickets, conversion, churn.',
                                                 'Slice dashboards by route, device, connection type, '
                                                 'release version.',
                                                 'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                               ('Ship checklist',
                                                ['Name invariant, owner, leading metric, and rollback path '
                                                 'before promote.',
                                                 'Link runbook from dashboard — not buried wiki.',
                                                 'Quarterly re-verify after browser releases and traffic '
                                                 'shifts.'])],
 'web-performance-will-change-sparingly': [('Why this breaks in production',
                                            ['will-change: transform on every list item consumed GPU memory '
                                             'until mobile browsers killed the tab — applying only during '
                                             'active animation saved 200MB.',
                                             '**When:** When animating transform/opacity and jank persists '
                                             'after other optimizations',
                                             '**Avoid:** Permanent will-change on static elements — memory '
                                             'leak on long sessions']),
                                           ('How it works',
                                            ['Production will-change used sparingly for compositor promotion '
                                             'requires explicit invariants, tests, and metrics — not '
                                             'checklist architecture diagrams.',
                                             'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                             'test for will-change used sparingly for compositor promotion.',
                                             'Rehearse anti-pattern in design review: Permanent will-change '
                                             'on static elements — memory leak on long sessions',
                                             'Rollback via feature flag or cache purge must be documented in '
                                             'the PR before merge.']),
                                           ('Implementation',
                                            ['Ship one route or endpoint first with metrics wired before '
                                             'broad rollout.',
                                             'Compare canary p75 to control for a full business day in '
                                             'target regions.',
                                             'Test refresh, back, double-submit, offline, and keyboard-only '
                                             'paths manually.']),
                                           ('Failure modes',
                                            ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                             'and test logged-in states.',
                                             'Third-party scripts change without your deploy — audit '
                                             'quarterly.',
                                             'Global metric averages hide regional or device-class '
                                             'regressions.']),
                                           ('Measurement',
                                            ['Leading: error rate, p75 latency, validation failures. '
                                             'Lagging: tickets, conversion, churn.',
                                             'Slice dashboards by route, device, connection type, release '
                                             'version.',
                                             'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                           ('Ship checklist',
                                            ['Name invariant, owner, leading metric, and rollback path '
                                             'before promote.',
                                             'Link runbook from dashboard — not buried wiki.',
                                             'Quarterly re-verify after browser releases and traffic '
                                             'shifts.'])],
 'web-popover-api-native': [('Why this breaks in production',
                             ['Our 400-line popover library fought with focus trap bugs — the native Popover '
                              "API with popover='auto' and invoker attributes replaced it in a afternoon "
                              'with better accessibility.',
                              '**When:** When tooltips, menus, and dropdowns need light-dismiss and '
                              'top-layer stacking',
                              '**Avoid:** Polyfilling Popover when 15% of users still need full keyboard and '
                              'light-dismiss behavior tested']),
                            ('How it works',
                             ['Production native Popover API with anchor positioning requires explicit '
                              'invariants, tests, and metrics — not checklist architecture diagrams.',
                              'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                              'native Popover API with anchor positioning.',
                              'Rehearse anti-pattern in design review: Polyfilling Popover when 15% of users '
                              'still need full keyboard and light-dismiss behavior tested',
                              'Rollback via feature flag or cache purge must be documented in the PR before '
                              'merge.']),
                            ('Implementation',
                             ['Ship one route or endpoint first with metrics wired before broad rollout.',
                              'Compare canary p75 to control for a full business day in target regions.',
                              'Test refresh, back, double-submit, offline, and keyboard-only paths '
                              'manually.']),
                            ('Failure modes',
                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                              'logged-in states.',
                              'Third-party scripts change without your deploy — audit quarterly.',
                              'Global metric averages hide regional or device-class regressions.']),
                            ('Measurement',
                             ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                              'conversion, churn.',
                              'Slice dashboards by route, device, connection type, release version.',
                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                            ('Ship checklist',
                             ['Name invariant, owner, leading metric, and rollback path before promote.',
                              'Link runbook from dashboard — not buried wiki.',
                              'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-scroll-snap-carousels': [('Why this breaks in production',
                                ['scroll-snap carousel with snap-align:center looked perfect on iPhone but '
                                 'cut off product titles on Android — scroll-padding and mandatory vs '
                                 'proximity fixed cross-browser snap.',
                                 '**When:** When horizontal product or image carousels need native touch '
                                 'scroll performance',
                                 '**Avoid:** mandatory snap on vertical scroll containers — hijacking page '
                                 'scroll on mobile']),
                               ('How it works',
                                ['Production CSS scroll-snap carousels without JavaScript requires explicit '
                                 'invariants, tests, and metrics — not checklist architecture diagrams.',
                                 'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                                 'CSS scroll-snap carousels without JavaScript.',
                                 'Rehearse anti-pattern in design review: mandatory snap on vertical scroll '
                                 'containers — hijacking page scroll on mobile',
                                 'Rollback via feature flag or cache purge must be documented in the PR '
                                 'before merge.']),
                               ('Implementation',
                                ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                 'Compare canary p75 to control for a full business day in target regions.',
                                 'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                 'manually.']),
                               ('Failure modes',
                                ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                 'logged-in states.',
                                 'Third-party scripts change without your deploy — audit quarterly.',
                                 'Global metric averages hide regional or device-class regressions.']),
                               ('Measurement',
                                ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                 'conversion, churn.',
                                 'Slice dashboards by route, device, connection type, release version.',
                                 'Alert week-over-week p75 regression on tier-1 surfaces.']),
                               ('Ship checklist',
                                ['Name invariant, owner, leading metric, and rollback path before promote.',
                                 'Link runbook from dashboard — not buried wiki.',
                                 'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-signals-fine-grained-reactivity': [('Why this breaks in production',
                                          ['Fine-grained signals updated only the price text node — our '
                                           'React re-render redrew the entire product grid on every stock '
                                           'tick.',
                                           '**When:** When high-frequency state changes hit large component '
                                           'trees',
                                           '**Avoid:** Using signals inside React without integration layer '
                                           '— double sources of truth']),
                                         ('How it works',
                                          ['Production JavaScript signals for fine-grained DOM updates '
                                           'requires explicit invariants, tests, and metrics — not checklist '
                                           'architecture diagrams.',
                                           'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                           'test for JavaScript signals for fine-grained DOM updates.',
                                           'Rehearse anti-pattern in design review: Using signals inside '
                                           'React without integration layer — double sources of truth',
                                           'Rollback via feature flag or cache purge must be documented in '
                                           'the PR before merge.']),
                                         ('Implementation',
                                          ['Ship one route or endpoint first with metrics wired before broad '
                                           'rollout.',
                                           'Compare canary p75 to control for a full business day in target '
                                           'regions.',
                                           'Test refresh, back, double-submit, offline, and keyboard-only '
                                           'paths manually.']),
                                         ('Failure modes',
                                          ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                           'test logged-in states.',
                                           'Third-party scripts change without your deploy — audit '
                                           'quarterly.',
                                           'Global metric averages hide regional or device-class '
                                           'regressions.']),
                                         ('Measurement',
                                          ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                           'tickets, conversion, churn.',
                                           'Slice dashboards by route, device, connection type, release '
                                           'version.',
                                           'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                         ('Ship checklist',
                                          ['Name invariant, owner, leading metric, and rollback path before '
                                           'promote.',
                                           'Link runbook from dashboard — not buried wiki.',
                                           'Quarterly re-verify after browser releases and traffic '
                                           'shifts.'])],
 'web-speculation-rules-prefetch': [('Why this breaks in production',
                                     ['Declarative speculation rules in HTTP headers prefetched admin routes '
                                      'for anonymous users — scoping rules by URL pattern and login cookie '
                                      'presence closed the leak.',
                                      '**When:** When MPAs have predictable next navigation from '
                                      'high-traffic entry pages',
                                      '**Avoid:** Global prefetch rules without excluding authenticated or '
                                      'personalized routes']),
                                    ('How it works',
                                     ['Production Speculation Rules prefetch in headers and markup requires '
                                      'explicit invariants, tests, and metrics — not checklist architecture '
                                      'diagrams.',
                                      'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                      'for Speculation Rules prefetch in headers and markup.',
                                      'Rehearse anti-pattern in design review: Global prefetch rules without '
                                      'excluding authenticated or personalized routes',
                                      'Rollback via feature flag or cache purge must be documented in the PR '
                                      'before merge.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-storage-indexeddb-patterns': [('Why this breaks in production',
                                     ['Storing chat history in localStorage hit the 5MB cap silently — '
                                      'IndexedDB with structured stores and eviction policy scaled to 200MB '
                                      'with clear upgrade migrations.',
                                      '**When:** When client data exceeds localStorage limits or needs '
                                      'indexing',
                                      '**Avoid:** No schema versioning — upgrade handlers that drop user '
                                      'data on deploy']),
                                    ('How it works',
                                     ['Production IndexedDB patterns for structured client storage requires '
                                      'explicit invariants, tests, and metrics — not checklist architecture '
                                      'diagrams.',
                                      'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                      'for IndexedDB patterns for structured client storage.',
                                      'Rehearse anti-pattern in design review: No schema versioning — '
                                      'upgrade handlers that drop user data on deploy',
                                      'Rollback via feature flag or cache purge must be documented in the PR '
                                      'before merge.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-view-transitions-multi-page': [('Why this breaks in production',
                                      ['View Transitions on MPAs made navigation feel instant — but back '
                                       'navigation showed wrong thumbnail until we synced '
                                       'view-transition-name on shared hero elements only.',
                                       '**When:** When MPAs want SPA-like transitions without full client '
                                       'routing',
                                       '**Avoid:** Same view-transition-name on multiple elements — broken '
                                       'cross-document transitions']),
                                     ('How it works',
                                      ['Production View Transitions API for multi-page apps requires '
                                       'explicit invariants, tests, and metrics — not checklist architecture '
                                       'diagrams.',
                                       'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                       'for View Transitions API for multi-page apps.',
                                       'Rehearse anti-pattern in design review: Same view-transition-name on '
                                       'multiple elements — broken cross-document transitions',
                                       'Rollback via feature flag or cache purge must be documented in the '
                                       'PR before merge.']),
                                     ('Implementation',
                                      ['Ship one route or endpoint first with metrics wired before broad '
                                       'rollout.',
                                       'Compare canary p75 to control for a full business day in target '
                                       'regions.',
                                       'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                       'manually.']),
                                     ('Failure modes',
                                      ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                       'test logged-in states.',
                                       'Third-party scripts change without your deploy — audit quarterly.',
                                       'Global metric averages hide regional or device-class regressions.']),
                                     ('Measurement',
                                      ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                       'tickets, conversion, churn.',
                                       'Slice dashboards by route, device, connection type, release version.',
                                       'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                     ('Ship checklist',
                                      ['Name invariant, owner, leading metric, and rollback path before '
                                       'promote.',
                                       'Link runbook from dashboard — not buried wiki.',
                                       'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-vitals-rum-dashboard-design': [('Why this breaks in production',
                                      ['Our RUM dashboard averaged LCP globally while India mobile p75 was '
                                       '4.2s — slicing by country, connection, and route exposed the real '
                                       'regressions.',
                                       '**When:** When lab Lighthouse scores disagree with field CrUX data',
                                       '**Avoid:** Single global LCP average without dimension breakdowns or '
                                       'lab vs field comparison']),
                                     ('How it works',
                                      ['Production RUM dashboard design for Core Web Vitals requires '
                                       'explicit invariants, tests, and metrics — not checklist architecture '
                                       'diagrams.',
                                       'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                       'for RUM dashboard design for Core Web Vitals.',
                                       'Rehearse anti-pattern in design review: Single global LCP average '
                                       'without dimension breakdowns or lab vs field comparison',
                                       'Rollback via feature flag or cache purge must be documented in the '
                                       'PR before merge.']),
                                     ('Implementation',
                                      ['Ship one route or endpoint first with metrics wired before broad '
                                       'rollout.',
                                       'Compare canary p75 to control for a full business day in target '
                                       'regions.',
                                       'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                       'manually.']),
                                     ('Failure modes',
                                      ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                       'test logged-in states.',
                                       'Third-party scripts change without your deploy — audit quarterly.',
                                       'Global metric averages hide regional or device-class regressions.']),
                                     ('Measurement',
                                      ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                       'tickets, conversion, churn.',
                                       'Slice dashboards by route, device, connection type, release version.',
                                       'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                     ('Ship checklist',
                                      ['Name invariant, owner, leading metric, and rollback path before '
                                       'promote.',
                                       'Link runbook from dashboard — not buried wiki.',
                                       'Quarterly re-verify after browser releases and traffic shifts.'])],
 'web-workers-offloading-compute': [('Why this breaks in production',
                                     ['Image thumbnail generation blocked checkout for three seconds on '
                                      'low-end Android — a Worker pool with two concurrent jobs kept the '
                                      'main thread responsive.',
                                      '**When:** When CPU-bound client tasks risk INP and long task '
                                      'violations',
                                      '**Avoid:** Spawning unbounded workers — exhausting memory on '
                                      'multi-file upload']),
                                    ('How it works',
                                     ['Production offloading compute to Web Worker pools requires explicit '
                                      'invariants, tests, and metrics — not checklist architecture diagrams.',
                                      'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                      'for offloading compute to Web Worker pools.',
                                      'Rehearse anti-pattern in design review: Spawning unbounded workers — '
                                      'exhausting memory on multi-file upload',
                                      'Rollback via feature flag or cache purge must be documented in the PR '
                                      'before merge.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webassembly-beyond-browser-wasi': [('Why this breaks in production',
                                      ['Running our WASM image filter on the server via WASI cut cold start '
                                       'vs container spin-up — same module on client and edge simplified the '
                                       'pipeline.',
                                       '**When:** When portable sandboxed modules should run on server, '
                                       'edge, or CLI',
                                       '**Avoid:** Assuming browser WASM (DOM imports) runs unchanged on '
                                       'WASI — different import namespace']),
                                     ('How it works',
                                      ['Production WebAssembly beyond the browser with WASI requires '
                                       'explicit invariants, tests, and metrics — not checklist architecture '
                                       'diagrams.',
                                       'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                       'for WebAssembly beyond the browser with WASI.',
                                       'Rehearse anti-pattern in design review: Assuming browser WASM (DOM '
                                       'imports) runs unchanged on WASI — different import namespace',
                                       'Rollback via feature flag or cache purge must be documented in the '
                                       'PR before merge.']),
                                     ('Implementation',
                                      ['Ship one route or endpoint first with metrics wired before broad '
                                       'rollout.',
                                       'Compare canary p75 to control for a full business day in target '
                                       'regions.',
                                       'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                       'manually.']),
                                     ('Failure modes',
                                      ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                       'test logged-in states.',
                                       'Third-party scripts change without your deploy — audit quarterly.',
                                       'Global metric averages hide regional or device-class regressions.']),
                                     ('Measurement',
                                      ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                       'tickets, conversion, churn.',
                                       'Slice dashboards by route, device, connection type, release version.',
                                       'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                     ('Ship checklist',
                                      ['Name invariant, owner, leading metric, and rollback path before '
                                       'promote.',
                                       'Link runbook from dashboard — not buried wiki.',
                                       'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webauthn-passkeys-server': [('Why this breaks in production',
                               ['Passkey registration succeeded in Chrome but Safari users could not sign in '
                                '— we had not configured related origins and allowed credential IDs per RP '
                                'ID.',
                                '**When:** When replacing passwords with platform authenticators and '
                                'syncable passkeys',
                                '**Avoid:** Storing only credential ID without signCount verification — '
                                'missing clone detection']),
                              ('How it works',
                               ['Production WebAuthn passkeys server verification and storage requires '
                                'explicit invariants, tests, and metrics — not checklist architecture '
                                'diagrams.',
                                'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                                'WebAuthn passkeys server verification and storage.',
                                'Rehearse anti-pattern in design review: Storing only credential ID without '
                                'signCount verification — missing clone detection',
                                'Rollback via feature flag or cache purge must be documented in the PR '
                                'before merge.']),
                              ('Implementation',
                               ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                'Compare canary p75 to control for a full business day in target regions.',
                                'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                'manually.']),
                              ('Failure modes',
                               ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                'logged-in states.',
                                'Third-party scripts change without your deploy — audit quarterly.',
                                'Global metric averages hide regional or device-class regressions.']),
                              ('Measurement',
                               ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                'conversion, churn.',
                                'Slice dashboards by route, device, connection type, release version.',
                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                              ('Ship checklist',
                               ['Name invariant, owner, leading metric, and rollback path before promote.',
                                'Link runbook from dashboard — not buried wiki.',
                                'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webgpu-compute-graphics': [('Why this breaks in production',
                              ['WebGL compute hacks for particle simulation hit driver bugs — WebGPU compute '
                               'shaders ran consistently across Chrome and Firefox with clearer buffer '
                               'lifecycle.',
                               '**When:** When WebGL limits block compute-style workloads or modern GPU '
                               'features',
                               '**Avoid:** Assuming WebGPU ships everywhere WebGL does — check adapter '
                               'availability and fallback']),
                             ('How it works',
                              ['Production WebGPU for compute and graphics in the browser requires explicit '
                               'invariants, tests, and metrics — not checklist architecture diagrams.',
                               'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                               'WebGPU for compute and graphics in the browser.',
                               'Rehearse anti-pattern in design review: Assuming WebGPU ships everywhere '
                               'WebGL does — check adapter availability and fallback',
                               'Rollback via feature flag or cache purge must be documented in the PR before '
                               'merge.']),
                             ('Implementation',
                              ['Ship one route or endpoint first with metrics wired before broad rollout.',
                               'Compare canary p75 to control for a full business day in target regions.',
                               'Test refresh, back, double-submit, offline, and keyboard-only paths '
                               'manually.']),
                             ('Failure modes',
                              ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                               'logged-in states.',
                               'Third-party scripts change without your deploy — audit quarterly.',
                               'Global metric averages hide regional or device-class regressions.']),
                             ('Measurement',
                              ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                               'conversion, churn.',
                               'Slice dashboards by route, device, connection type, release version.',
                               'Alert week-over-week p75 regression on tier-1 surfaces.']),
                             ('Ship checklist',
                              ['Name invariant, owner, leading metric, and rollback path before promote.',
                               'Link runbook from dashboard — not buried wiki.',
                               'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webhooks-reliable-delivery': [('Why this breaks in production',
                                 ['Webhooks looked trivial until a consumer outage silently dropped events — '
                                  'persist-first delivery with backoff turned integrations from complaint '
                                  'magnets into dependable contracts.',
                                  '**When:** When partners depend on event notifications for billing, '
                                  'fulfillment, or sync',
                                  '**Avoid:** Fire-and-forget POST without durable queue or retry policy']),
                                ('How it works',
                                 ['Write webhook obligations to an outbox in the same DB transaction as the '
                                  'business event. Workers claim with FOR UPDATE SKIP LOCKED.',
                                  'Retry with exponential backoff and full jitter; dead-letter after max '
                                  'attempts. Sign HMAC over raw body plus timestamp.',
                                  'At-least-once delivery requires consumer dedupe on stable event_id. '
                                  'Return 200 on duplicate so sender stops retrying.']),
                                ('Implementation',
                                 ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                  'Compare canary p75 to control for a full business day in target regions.',
                                  'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                  'manually.']),
                                ('Failure modes',
                                 ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                  'logged-in states.',
                                  'Third-party scripts change without your deploy — audit quarterly.',
                                  'Global metric averages hide regional or device-class regressions.']),
                                ('Measurement',
                                 ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                  'conversion, churn.',
                                  'Slice dashboards by route, device, connection type, release version.',
                                  'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                ('Ship checklist',
                                 ['Name invariant, owner, leading metric, and rollback path before promote.',
                                  'Link runbook from dashboard — not buried wiki.',
                                  'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webhooks-retry-idempotency': [('Why this breaks in production',
                                 ['Double webhook delivery double-charged a customer because our handler '
                                  'keyed idempotency on timestamp instead of event ID — stable IDs fixed '
                                  'reconciliation.',
                                  '**When:** When at-least-once delivery means duplicate POSTs are '
                                  'guaranteed',
                                  '**Avoid:** Idempotency keys that change per retry attempt instead of '
                                  'stable event identifiers']),
                                ('How it works',
                                 ['Production webhook retry idempotency on consumer side requires explicit '
                                  'invariants, tests, and metrics — not checklist architecture diagrams.',
                                  'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                                  'webhook retry idempotency on consumer side.',
                                  'Rehearse anti-pattern in design review: Idempotency keys that change per '
                                  'retry attempt instead of stable event identifiers',
                                  'Rollback via feature flag or cache purge must be documented in the PR '
                                  'before merge.']),
                                ('Implementation',
                                 ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                  'Compare canary p75 to control for a full business day in target regions.',
                                  'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                  'manually.']),
                                ('Failure modes',
                                 ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                  'logged-in states.',
                                  'Third-party scripts change without your deploy — audit quarterly.',
                                  'Global metric averages hide regional or device-class regressions.']),
                                ('Measurement',
                                 ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                  'conversion, churn.',
                                  'Slice dashboards by route, device, connection type, release version.',
                                  'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                ('Ship checklist',
                                 ['Name invariant, owner, leading metric, and rollback path before promote.',
                                  'Link runbook from dashboard — not buried wiki.',
                                  'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webhooks-signature-verification': [('Why this breaks in production',
                                      ['We verified HMAC over parsed JSON instead of raw body — key '
                                       'reordering in transit caused false rejections and a partner '
                                       'integration outage.',
                                       '**When:** When webhook endpoints must reject forged or tampered '
                                       'payloads',
                                       '**Avoid:** Re-serializing JSON for verification instead of using raw '
                                       'request bytes']),
                                     ('How it works',
                                      ['Production webhook HMAC signature verification on raw body requires '
                                       'explicit invariants, tests, and metrics — not checklist architecture '
                                       'diagrams.',
                                       'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                       'for webhook HMAC signature verification on raw body.',
                                       'Rehearse anti-pattern in design review: Re-serializing JSON for '
                                       'verification instead of using raw request bytes',
                                       'Rollback via feature flag or cache purge must be documented in the '
                                       'PR before merge.']),
                                     ('Implementation',
                                      ['Ship one route or endpoint first with metrics wired before broad '
                                       'rollout.',
                                       'Compare canary p75 to control for a full business day in target '
                                       'regions.',
                                       'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                       'manually.']),
                                     ('Failure modes',
                                      ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                       'test logged-in states.',
                                       'Third-party scripts change without your deploy — audit quarterly.',
                                       'Global metric averages hide regional or device-class regressions.']),
                                     ('Measurement',
                                      ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                       'tickets, conversion, churn.',
                                       'Slice dashboards by route, device, connection type, release version.',
                                       'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                     ('Ship checklist',
                                      ['Name invariant, owner, leading metric, and rollback path before '
                                       'promote.',
                                       'Link runbook from dashboard — not buried wiki.',
                                       'Quarterly re-verify after browser releases and traffic shifts.'])],
 'webrtc-data-channels-realtime': [('Why this breaks in production',
                                    ['WebSocket relay cost scaled linearly with video adjacency chat — '
                                     'WebRTC data channels for game state cut server bandwidth 90% after ICE '
                                     'negotiation.',
                                     '**When:** When low-latency peer data beats server fan-out for games or '
                                     'collaboration',
                                     '**Avoid:** No TURN server fallback — corporate NAT blocks 30% of P2P '
                                     'connections']),
                                   ('How it works',
                                    ['Production WebRTC data channels for peer realtime data requires '
                                     'explicit invariants, tests, and metrics — not checklist architecture '
                                     'diagrams.',
                                     'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                     'for WebRTC data channels for peer realtime data.',
                                     'Rehearse anti-pattern in design review: No TURN server fallback — '
                                     'corporate NAT blocks 30% of P2P connections',
                                     'Rollback via feature flag or cache purge must be documented in the PR '
                                     'before merge.']),
                                   ('Implementation',
                                    ['Ship one route or endpoint first with metrics wired before broad '
                                     'rollout.',
                                     'Compare canary p75 to control for a full business day in target '
                                     'regions.',
                                     'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                     'manually.']),
                                   ('Failure modes',
                                    ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                     'logged-in states.',
                                     'Third-party scripts change without your deploy — audit quarterly.',
                                     'Global metric averages hide regional or device-class regressions.']),
                                   ('Measurement',
                                    ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                     'tickets, conversion, churn.',
                                     'Slice dashboards by route, device, connection type, release version.',
                                     'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                   ('Ship checklist',
                                    ['Name invariant, owner, leading metric, and rollback path before '
                                     'promote.',
                                     'Link runbook from dashboard — not buried wiki.',
                                     'Quarterly re-verify after browser releases and traffic shifts.'])],
 'websocket-heartbeat-ping-pong': [('Why this breaks in production',
                                    ['Idle WebSocket connections dropped by AWS ALB after 60s without us '
                                     'knowing — application-level ping every 30s kept connections alive and '
                                     'detected dead peers.',
                                     '**When:** When proxies and load balancers silently drop idle WebSocket '
                                     'connections',
                                     '**Avoid:** Relying on TCP keepalive alone — insufficient through L7 '
                                     'load balancers']),
                                   ('How it works',
                                    ['Production WebSocket heartbeat ping-pong patterns requires explicit '
                                     'invariants, tests, and metrics — not checklist architecture diagrams.',
                                     'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                     'for WebSocket heartbeat ping-pong patterns.',
                                     'Rehearse anti-pattern in design review: Relying on TCP keepalive alone '
                                     '— insufficient through L7 load balancers',
                                     'Rollback via feature flag or cache purge must be documented in the PR '
                                     'before merge.']),
                                   ('Implementation',
                                    ['Ship one route or endpoint first with metrics wired before broad '
                                     'rollout.',
                                     'Compare canary p75 to control for a full business day in target '
                                     'regions.',
                                     'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                     'manually.']),
                                   ('Failure modes',
                                    ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                     'logged-in states.',
                                     'Third-party scripts change without your deploy — audit quarterly.',
                                     'Global metric averages hide regional or device-class regressions.']),
                                   ('Measurement',
                                    ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                     'tickets, conversion, churn.',
                                     'Slice dashboards by route, device, connection type, release version.',
                                     'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                   ('Ship checklist',
                                    ['Name invariant, owner, leading metric, and rollback path before '
                                     'promote.',
                                     'Link runbook from dashboard — not buried wiki.',
                                     'Quarterly re-verify after browser releases and traffic shifts.'])],
 'websocket-reconnection-backoff': [('Why this breaks in production',
                                     ['Instant reconnect on WebSocket drop hammered our recovering server — '
                                      'exponential backoff with jitter spread reconnects across two minutes '
                                      'instead of one spike.',
                                      '**When:** When clients must survive server deploys and network blips',
                                      '**Avoid:** Immediate reconnect loops without max delay or jitter']),
                                    ('How it works',
                                     ['Production WebSocket reconnection with exponential backoff requires '
                                      'explicit invariants, tests, and metrics — not checklist architecture '
                                      'diagrams.',
                                      'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                      'for WebSocket reconnection with exponential backoff.',
                                      'Rehearse anti-pattern in design review: Immediate reconnect loops '
                                      'without max delay or jitter',
                                      'Rollback via feature flag or cache purge must be documented in the PR '
                                      'before merge.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'whats-new-android-17': [('Why this breaks in production',
                           ['Android 17 tightened foreground service types again — our tracking app got '
                            'rejected until we migrated to the new health sync API and declared FGS types '
                            'explicitly.',
                            '**When:** When targeting API 37 and updating Play policy compliance',
                            '**Avoid:** Assuming Android 16 behavior without reading behavior changes doc '
                            'for background work']),
                          ('How it works',
                           ['Production Android 17 platform changes for app developers requires explicit '
                            'invariants, tests, and metrics — not checklist architecture diagrams.',
                            'Field p75 on mid-tier Android over 4G is the honest acceptance test for Android '
                            '17 platform changes for app developers.',
                            'Rehearse anti-pattern in design review: Assuming Android 16 behavior without '
                            'reading behavior changes doc for background work',
                            'Rollback via feature flag or cache purge must be documented in the PR before '
                            'merge.']),
                          ('Implementation',
                           ['Ship one route or endpoint first with metrics wired before broad rollout.',
                            'Compare canary p75 to control for a full business day in target regions.',
                            'Test refresh, back, double-submit, offline, and keyboard-only paths manually.']),
                          ('Failure modes',
                           ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test logged-in '
                            'states.',
                            'Third-party scripts change without your deploy — audit quarterly.',
                            'Global metric averages hide regional or device-class regressions.']),
                          ('Measurement',
                           ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                            'conversion, churn.',
                            'Slice dashboards by route, device, connection type, release version.',
                            'Alert week-over-week p75 regression on tier-1 surfaces.']),
                          ('Ship checklist',
                           ['Name invariant, owner, leading metric, and rollback path before promote.',
                            'Link runbook from dashboard — not buried wiki.',
                            'Quarterly re-verify after browser releases and traffic shifts.'])],
 'workmanager-reliable-background-work': [('Why this breaks in production',
                                           ['AlarmManager exact alarms drained battery and still missed sync '
                                            'on Doze — WorkManager with expedited workers and network '
                                            'constraints matched Android power policies.',
                                            '**When:** When deferrable sync, upload, or cleanup must survive '
                                            'process death and Doze',
                                            '**Avoid:** Raw Thread or GlobalScope for background work — '
                                            'killed by OEM battery savers']),
                                          ('How it works',
                                           ['Production WorkManager for reliable background work on Android '
                                            'requires explicit invariants, tests, and metrics — not '
                                            'checklist architecture diagrams.',
                                            'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                            'test for WorkManager for reliable background work on Android.',
                                            'Rehearse anti-pattern in design review: Raw Thread or '
                                            'GlobalScope for background work — killed by OEM battery savers',
                                            'Rollback via feature flag or cache purge must be documented in '
                                            'the PR before merge.']),
                                          ('Implementation',
                                           ['Ship one route or endpoint first with metrics wired before '
                                            'broad rollout.',
                                            'Compare canary p75 to control for a full business day in target '
                                            'regions.',
                                            'Test refresh, back, double-submit, offline, and keyboard-only '
                                            'paths manually.']),
                                          ('Failure modes',
                                           ['Staging on office Wi-Fi with empty cache misleads — warm CDN '
                                            'and test logged-in states.',
                                            'Third-party scripts change without your deploy — audit '
                                            'quarterly.',
                                            'Global metric averages hide regional or device-class '
                                            'regressions.']),
                                          ('Measurement',
                                           ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                            'tickets, conversion, churn.',
                                            'Slice dashboards by route, device, connection type, release '
                                            'version.',
                                            'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                          ('Ship checklist',
                                           ['Name invariant, owner, leading metric, and rollback path before '
                                            'promote.',
                                            'Link runbook from dashboard — not buried wiki.',
                                            'Quarterly re-verify after browser releases and traffic '
                                            'shifts.'])],
 'xss-dom-based-prevention': [('Why this breaks in production',
                               ['location.hash fed into innerHTML without sanitization — a crafted link '
                                'exfiltrated session tokens via DOM XSS that WAF never saw because payload '
                                'never hit the server.',
                                '**When:** When URL fragments, postMessage, or client storage flow into DOM '
                                'sinks',
                                '**Avoid:** Trusting client-side routing params for document.write or eval '
                                'sinks']),
                              ('How it works',
                               ['Production DOM-based XSS prevention in client-rendered apps requires '
                                'explicit invariants, tests, and metrics — not checklist architecture '
                                'diagrams.',
                                'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                                'DOM-based XSS prevention in client-rendered apps.',
                                'Rehearse anti-pattern in design review: Trusting client-side routing params '
                                'for document.write or eval sinks',
                                'Rollback via feature flag or cache purge must be documented in the PR '
                                'before merge.']),
                              ('Implementation',
                               ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                'Compare canary p75 to control for a full business day in target regions.',
                                'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                'manually.']),
                              ('Failure modes',
                               ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                'logged-in states.',
                                'Third-party scripts change without your deploy — audit quarterly.',
                                'Global metric averages hide regional or device-class regressions.']),
                              ('Measurement',
                               ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                'conversion, churn.',
                                'Slice dashboards by route, device, connection type, release version.',
                                'Alert week-over-week p75 regression on tier-1 surfaces.']),
                              ('Ship checklist',
                               ['Name invariant, owner, leading metric, and rollback path before promote.',
                                'Link runbook from dashboard — not buried wiki.',
                                'Quarterly re-verify after browser releases and traffic shifts.'])],
 'xss-prevention-csp-trusted-types': [('Why this breaks in production',
                                       ['Trusted Types policy blocked a marketing tag injection — we moved '
                                        'analytics to nonce-based CSP and registered a default policy for '
                                        'app-owned sinks only.',
                                        '**When:** When reflected and stored XSS defenses need enforceable '
                                        'browser policies',
                                        '**Avoid:** Report-Only CSP forever — never enforcing because third '
                                        'parties break']),
                                      ('How it works',
                                       ['Production CSP and Trusted Types for XSS prevention requires '
                                        'explicit invariants, tests, and metrics — not checklist '
                                        'architecture diagrams.',
                                        'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                        'for CSP and Trusted Types for XSS prevention.',
                                        'Rehearse anti-pattern in design review: Report-Only CSP forever — '
                                        'never enforcing because third parties break',
                                        'Rollback via feature flag or cache purge must be documented in the '
                                        'PR before merge.']),
                                      ('Implementation',
                                       ['Ship one route or endpoint first with metrics wired before broad '
                                        'rollout.',
                                        'Compare canary p75 to control for a full business day in target '
                                        'regions.',
                                        'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                        'manually.']),
                                      ('Failure modes',
                                       ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                        'test logged-in states.',
                                        'Third-party scripts change without your deploy — audit quarterly.',
                                        'Global metric averages hide regional or device-class regressions.']),
                                      ('Measurement',
                                       ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                        'tickets, conversion, churn.',
                                        'Slice dashboards by route, device, connection type, release '
                                        'version.',
                                        'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                      ('Ship checklist',
                                       ['Name invariant, owner, leading metric, and rollback path before '
                                        'promote.',
                                        'Link runbook from dashboard — not buried wiki.',
                                        'Quarterly re-verify after browser releases and traffic shifts.'])],
 'xss-sanitize-html-user-content': [('Why this breaks in production',
                                     ['DOMPurify blocked script but allowed onerror on SVG — tightening '
                                      'ALLOWED_TAGS and using hook to strip event handlers stopped stored '
                                      'XSS in comment previews.',
                                      '**When:** When rich text comments, bios, or CMS content renders as '
                                      'HTML',
                                      '**Avoid:** Regex strip of script tags — misses img onerror, '
                                      'javascript: URLs, and SVG vectors']),
                                    ('How it works',
                                     ['Production sanitize HTML user content with allowlists requires '
                                      'explicit invariants, tests, and metrics — not checklist architecture '
                                      'diagrams.',
                                      'Field p75 on mid-tier Android over 4G is the honest acceptance test '
                                      'for sanitize HTML user content with allowlists.',
                                      'Rehearse anti-pattern in design review: Regex strip of script tags — '
                                      'misses img onerror, javascript: URLs, and SVG vectors',
                                      'Rollback via feature flag or cache purge must be documented in the PR '
                                      'before merge.']),
                                    ('Implementation',
                                     ['Ship one route or endpoint first with metrics wired before broad '
                                      'rollout.',
                                      'Compare canary p75 to control for a full business day in target '
                                      'regions.',
                                      'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                      'manually.']),
                                    ('Failure modes',
                                     ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                      'logged-in states.',
                                      'Third-party scripts change without your deploy — audit quarterly.',
                                      'Global metric averages hide regional or device-class regressions.']),
                                    ('Measurement',
                                     ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                      'tickets, conversion, churn.',
                                      'Slice dashboards by route, device, connection type, release version.',
                                      'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                    ('Ship checklist',
                                     ['Name invariant, owner, leading metric, and rollback path before '
                                      'promote.',
                                      'Link runbook from dashboard — not buried wiki.',
                                      'Quarterly re-verify after browser releases and traffic shifts.'])],
 'zero-downtime-database-migrations': [('Why this breaks in production',
                                        ['Adding NOT NULL column without default locked the users table for '
                                         'four minutes — expand-contract with nullable column, backfill, '
                                         'then enforce recovered zero downtime.',
                                         '**When:** When schema changes must ship without maintenance '
                                         'windows on large tables',
                                         '**Avoid:** Direct ALTER on million-row tables during peak '
                                         'traffic']),
                                       ('How it works',
                                        ['Production zero-downtime database migrations with expand-contract '
                                         'requires explicit invariants, tests, and metrics — not checklist '
                                         'architecture diagrams.',
                                         'Field p75 on mid-tier Android over 4G is the honest acceptance '
                                         'test for zero-downtime database migrations with expand-contract.',
                                         'Rehearse anti-pattern in design review: Direct ALTER on '
                                         'million-row tables during peak traffic',
                                         'Rollback via feature flag or cache purge must be documented in the '
                                         'PR before merge.']),
                                       ('Implementation',
                                        ['Ship one route or endpoint first with metrics wired before broad '
                                         'rollout.',
                                         'Compare canary p75 to control for a full business day in target '
                                         'regions.',
                                         'Test refresh, back, double-submit, offline, and keyboard-only '
                                         'paths manually.']),
                                       ('Failure modes',
                                        ['Staging on office Wi-Fi with empty cache misleads — warm CDN and '
                                         'test logged-in states.',
                                         'Third-party scripts change without your deploy — audit quarterly.',
                                         'Global metric averages hide regional or device-class '
                                         'regressions.']),
                                       ('Measurement',
                                        ['Leading: error rate, p75 latency, validation failures. Lagging: '
                                         'tickets, conversion, churn.',
                                         'Slice dashboards by route, device, connection type, release '
                                         'version.',
                                         'Alert week-over-week p75 regression on tier-1 surfaces.']),
                                       ('Ship checklist',
                                        ['Name invariant, owner, leading metric, and rollback path before '
                                         'promote.',
                                         'Link runbook from dashboard — not buried wiki.',
                                         'Quarterly re-verify after browser releases and traffic shifts.'])],
 'zero-trust-mobile-apps': [('Why this breaks in production',
                             ['VPN tunneling all mobile traffic failed compliance — zero trust with per-app '
                              'attestation, device posture checks, and short-lived tokens matched how field '
                              'reps actually work.',
                              '**When:** When corporate data on BYOD devices needs least-privilege access '
                              'without legacy VPN',
                              '**Avoid:** Binary allow/deny VPN instead of continuous verification and '
                              'step-up auth']),
                            ('How it works',
                             ['Production zero trust architecture for mobile apps requires explicit '
                              'invariants, tests, and metrics — not checklist architecture diagrams.',
                              'Field p75 on mid-tier Android over 4G is the honest acceptance test for zero '
                              'trust architecture for mobile apps.',
                              'Rehearse anti-pattern in design review: Binary allow/deny VPN instead of '
                              'continuous verification and step-up auth',
                              'Rollback via feature flag or cache purge must be documented in the PR before '
                              'merge.']),
                            ('Implementation',
                             ['Ship one route or endpoint first with metrics wired before broad rollout.',
                              'Compare canary p75 to control for a full business day in target regions.',
                              'Test refresh, back, double-submit, offline, and keyboard-only paths '
                              'manually.']),
                            ('Failure modes',
                             ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                              'logged-in states.',
                              'Third-party scripts change without your deploy — audit quarterly.',
                              'Global metric averages hide regional or device-class regressions.']),
                            ('Measurement',
                             ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                              'conversion, churn.',
                              'Slice dashboards by route, device, connection type, release version.',
                              'Alert week-over-week p75 regression on tier-1 surfaces.']),
                            ('Ship checklist',
                             ['Name invariant, owner, leading metric, and rollback path before promote.',
                              'Link runbook from dashboard — not buried wiki.',
                              'Quarterly re-verify after browser releases and traffic shifts.'])],
 'zero-trust-network-access': [('Why this breaks in production',
                                ['Flat network access let a compromised laptop reach every internal service '
                                 '— ZTNA with identity-aware proxies reduced blast radius to authorized app '
                                 'segments only.',
                                 '**When:** When remote workforce needs app-level access without full '
                                 'network trust',
                                 '**Avoid:** ZTNA vendor without logging and policy testing — black box '
                                 'allow rules']),
                               ('How it works',
                                ['Production zero-trust network access replacing perimeter VPN requires '
                                 'explicit invariants, tests, and metrics — not checklist architecture '
                                 'diagrams.',
                                 'Field p75 on mid-tier Android over 4G is the honest acceptance test for '
                                 'zero-trust network access replacing perimeter VPN.',
                                 'Rehearse anti-pattern in design review: ZTNA vendor without logging and '
                                 'policy testing — black box allow rules',
                                 'Rollback via feature flag or cache purge must be documented in the PR '
                                 'before merge.']),
                               ('Implementation',
                                ['Ship one route or endpoint first with metrics wired before broad rollout.',
                                 'Compare canary p75 to control for a full business day in target regions.',
                                 'Test refresh, back, double-submit, offline, and keyboard-only paths '
                                 'manually.']),
                               ('Failure modes',
                                ['Staging on office Wi-Fi with empty cache misleads — warm CDN and test '
                                 'logged-in states.',
                                 'Third-party scripts change without your deploy — audit quarterly.',
                                 'Global metric averages hide regional or device-class regressions.']),
                               ('Measurement',
                                ['Leading: error rate, p75 latency, validation failures. Lagging: tickets, '
                                 'conversion, churn.',
                                 'Slice dashboards by route, device, connection type, release version.',
                                 'Alert week-over-week p75 regression on tier-1 surfaces.']),
                               ('Ship checklist',
                                ['Name invariant, owner, leading metric, and rollback path before promote.',
                                 'Link runbook from dashboard — not buried wiki.',
                                 'Quarterly re-verify after browser releases and traffic shifts.'])]}
