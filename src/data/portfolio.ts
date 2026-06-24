export type HeroLink = {
  label: string;
  href: string;
  icon: "book" | "github" | "linkedin" | "store";
};

export type HeroData = {
  name: string;
  title: string;
  status: string;
  statusAvailable: boolean;
  email: string;
  location: string;
  headline: string;
  links: HeroLink[];
};

export type ProjectData = {
  id: string;
  title: string;
  company: string;
  description: string;
  tags: string[];
  links: { label: string; href: string }[];
  media:
    | { type: "image"; src: string; alt: string }
    | { type: "video"; src: string; poster?: string; alt?: string }
    | { type: "terminal"; terminalLines: string[] };
  highlight?: boolean;
  year: string;
};

export type ExperienceData = {
  role: string;
  company: string;
  companyUrl?: string;
  period: { start: string; end: string | "Present" };
  bullets: string[];
  isCurrent: boolean;
};

export const site = {
  origin: "https://michaelsam94.tech",
  canonicalOrigin: "https://michaelsam94.com",
  name: "Michael Samuel Naeem",
  shortName: "Michael Sam",
  description:
    "Senior Android engineer and mobile architect building production Kotlin, Jetpack Compose, Flutter, robotics, EV infrastructure, and developer tooling.",
};

export const profile = {
  name: "Michael Samuel Naeem",
  title: "Senior / Staff Android Engineer · Mobile Architect",
  tagline: "EV Infrastructure · Robotics · Real-Time Systems",
  location: "Cairo, Egypt",
  email: "michaelsam00@yahoo.com",
  phone: "+20 109 800 2198",
  linkedin: "https://www.linkedin.com/in/michaelsam00/",
  github: "https://github.com/michaelsam94",
  techBlog: "/blog/",
  vscodeMarketplace: "https://marketplace.visualstudio.com/publishers/MichaelSam94",
  openVsx: "https://open-vsx.org/namespace/michaelsam94",
  playStoreDeveloper: "https://play.google.com/store/apps/developer?id=MichaelSam94",
  cvUrl: "/Michael_Samuel_Naeem_Mobile_Developer_CV.pdf",
  avatar: "/profile-photo.png",
  heroAvatar: "/profile-photo-hero.webp",
  avatarAlt: "Michael Samuel Naeem, senior Android developer and tech lead based in Cairo, Egypt.",
  headline:
    "I architect and ship production mobile systems across Android, Flutter, robotics, EV charging, fintech, and real-time streaming.",
};

export const heroData: HeroData = {
  name: "Michael Sam",
  title: "Senior Android Engineer & Mobile Architect",
  status: "Available for remote senior roles",
  statusAvailable: true,
  email: profile.email,
  location: "Cairo, EG",
  headline:
    "I build mobile systems that survive production: robot interfaces, OCPP charging networks, live auction streaming, fintech wallets, and offline-first Android tools.",
  links: [
    { label: "GitHub", href: profile.github, icon: "github" },
    { label: "LinkedIn", href: profile.linkedin, icon: "linkedin" },
    { label: "Play Store", href: profile.playStoreDeveloper, icon: "store" },
    { label: "Writing", href: profile.techBlog, icon: "book" },
  ],
};

export const about = {
  summary:
    "I am Michael Samuel Naeem, a senior Android developer and mobile architect with 10+ years shipping production apps and 4+ years leading engineers. I work closest to the places where mobile UX, backend contracts, real-time systems, and release quality meet.",
  highlights: [
    "Architected Android and Flutter systems for EV charging, robotics, fintech, e-commerce, live streaming, and developer tooling.",
    "Led teams of 4-6 engineers while staying hands-on with Kotlin, Jetpack Compose, Flutter, architecture, performance, and release quality.",
    "Shipped public Google Play apps and VS Code extensions under MichaelSam94, with static documentation and crawlable product pages.",
    "Comfortable joining messy systems: audit the risk, name the tradeoffs, reduce ambiguity, then ship the next useful milestone.",
  ],
};

export const impactMetrics = [
  { value: "10+", label: "years shipping", detail: "Android, Flutter, robotics, EV charging, fintech, commerce, and tools." },
  { value: "4+", label: "years leading", detail: "Hands-on technical leadership across squads, architecture, mentoring, and delivery." },
  { value: "120k+", label: "MAU supported", detail: "Live auction and commerce workflows with streaming and real-time interaction." },
  { value: "240+", label: "categories shipped", detail: "Service marketplace delivery with Compose, MVVM, and production release work." },
  { value: "99.9%", label: "crash-free targets", detail: "Production Android reliability through profiling, architecture, and release discipline." },
  { value: "24", label: "Android apps", detail: "Published Google Play catalog across utilities, finance, privacy, scanners, and developer tools." },
  { value: "9", label: "VS Code extensions", detail: "Document, CSV, PDF, Markdown, DOCX, and AI-context workflow extensions." },
  { value: "0", label: "hero fluff", detail: "No carousel theater; just proof, links, and work someone can inspect." },
] as const;

export const answerHub = [
  {
    question: "Can you help my team ship a reliable Android app?",
    answer:
      "Yes. I build Kotlin and Jetpack Compose apps with cleaner architecture, faster screens, fewer crashes, and releases your team can trust.",
  },
  {
    question: "What do you bring beyond writing code?",
    answer:
      "Architecture judgement, delivery sequencing, mentoring, code review, production debugging, and the ability to make technical tradeoffs plain.",
  },
  {
    question: "Can we work together outside Egypt?",
    answer:
      "Yes. I am based in Cairo and work with remote teams across the United States, Europe, the Gulf region, and nearby time zones.",
  },
  {
    question: "What projects are the strongest fit?",
    answer:
      "Android, Kotlin, Flutter, real-time systems, OCPP, EV charging, robotics interfaces, developer tools, AI automation, and production rescue work.",
  },
] as const;

export const workGuide = [
  {
    question: "What should you send first?",
    answer:
      "Send the product goal, current stack, affected users, deadline, and any crash logs, screenshots, store reviews, or short recordings.",
  },
  {
    question: "How do we start?",
    answer:
      "We agree on the outcome, map the riskiest parts, and choose the smallest useful milestone before writing more code.",
  },
  {
    question: "What happens when something is risky?",
    answer:
      "I will say it plainly, explain the tradeoff, and propose a practical path if scope, architecture, or timeline looks fragile.",
  },
  {
    question: "Can you join an existing team?",
    answer:
      "Yes. I can pair with your team, review pull requests, lead a feature stream, or help Android, Flutter, React, and backend work connect.",
  },
] as const;

export const skillGroups = [
  { title: "Mobile", items: ["Android", "Kotlin", "Java", "Flutter", "Dart", "Jetpack Compose", "Android TV"] },
  { title: "Architecture", items: ["Clean Architecture", "MVVM", "MVI", "Modularization", "ADRs", "Repository patterns"] },
  { title: "Async & DI", items: ["Coroutines", "Flow", "RxJava", "Hilt", "Dagger 2", "Koin"] },
  { title: "Networking", items: ["REST", "GraphQL", "WebSocket", "OCPP 1.6", "Retrofit", "OkHttp", "Ktor"] },
  { title: "Media & IoT", items: ["WebRTC", "ExoPlayer", "Robot SDKs", "BLE", "CameraX", "ML Kit", "DSP"] },
  { title: "Data", items: ["Room", "SQLite", "DataStore", "Firebase", "Supabase", "Offline-first sync"] },
  { title: "AI & Tools", items: ["OpenAI", "On-device AI", "OCR", "VS Code Extension API", "TypeScript", "Node.js"] },
  { title: "Quality", items: ["JUnit", "Robolectric", "Roborazzi", "CI", "Crashlytics", "Profiling", "Play Console"] },
] as const;

export const certifications = [
  { name: "Android Development", org: "Production experience", year: "10+ years" },
  { name: "Flutter Delivery", org: "Production apps", year: "2024" },
  { name: "Technical Leadership", org: "Team lead practice", year: "4+ years" },
  { name: "Google Play Publishing", org: "MichaelSam94 catalog", year: "2025-2026" },
] as const;

export const motionVideos = [
  {
    title: "Samsung Galaxy Watch 8 | Cinematic Motion Design Reel",
    description:
      "Product launch concept exploring macro texture reveals, orbital camera sweeps, data UI motion, chrome material language, and hard-stop brand lockup.",
    src: "/motion/storyboard-motion-video.mp4",
  },
  {
    title: "Khamrah by Lattafa | Motion Design",
    description:
      "Luxury fragrance film concept built around crystal bottle facets, amber liquid, black/gold material contrast, and cinematic product pacing.",
    src: "/motion/luxury-performance-motion.mp4",
  },
] as const;

export const openSourceHighlights = [
  {
    title: "GitHub Portfolio",
    description: "Public Android, Flutter, TypeScript, VS Code extension, document-tooling, and learning repositories.",
    href: profile.github,
    meta: "michaelsam94",
  },
  {
    title: "VS Code Extensions",
    description: "Open developer tools for Markdown, PDF, DOCX, CSV, context export, and document workflows.",
    href: profile.vscodeMarketplace,
    meta: "9 extensions",
  },
  {
    title: "Android App Sources",
    description: "Companion repositories for published Play Store apps, privacy-first tools, local utilities, and experiments.",
    href: `${profile.github}?tab=repositories`,
    meta: "Kotlin / Compose",
  },
] as const;

export const projectsData: ProjectData[] = [
  {
    id: "ev-charging",
    title: "EV Charging Management Platform",
    company: "Tadafuq · Mega Plug",
    description:
      "Full-stack EV charging platform spanning Python OCPP v1.6, Node.js WebSocket middleware, and Flutter control surfaces with sub-100ms local-network sync.",
    tags: ["Flutter", "OCPP", "WebSocket", "IoT", "Python"],
    links: [{ label: "Play listing", href: "https://play.google.com/store/apps/details?id=com.mega.plug" }],
    media: {
      type: "terminal",
      terminalLines: [
        "$ ocpp/session boot",
        "charger.handshake: accepted",
        "meter.sync: 83ms p95",
        "faults.critical: 0 post-launch",
      ],
    },
    highlight: true,
    year: "2024",
  },
  {
    id: "neom-robotics",
    title: "NEOM Humanoid Robotics",
    company: "Communico",
    description:
      "Android interfaces for CRUZR and Pepper robots with GPT-4 intent recognition, STT/TTS, touchscreen flows, and SDK integration for thousands of daily interactions.",
    tags: ["Kotlin", "Robot SDK", "OpenAI", "STT/TTS"],
    links: [{ label: "GitHub", href: profile.github }],
    media: {
      type: "terminal",
      terminalLines: ["intent.match: +35%", "handoff.rate: reduced", "uptime: 99%+", "sdk.modules: 4"],
    },
    highlight: true,
    year: "2023",
  },
  {
    id: "mazaady-live",
    title: "Mazaady Live Auction",
    company: "Mazaady",
    description:
      "Real-time Android commerce stack with ExoPlayer and WebRTC for live auctions serving 120k+ monthly active users and low-ANR production builds.",
    tags: ["WebRTC", "ExoPlayer", "Compose", "MVVM"],
    links: [{ label: "Play listing", href: "https://play.google.com/store/apps/details?id=com.mazaady" }],
    media: {
      type: "terminal",
      terminalLines: ["stream.join: stable", "mau: 120k+", "engagement: +20%", "anr: <0.1%"],
    },
    year: "2022",
  },
  {
    id: "insightlyspend",
    title: "InsightlySpend",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline-first Android finance app for wallets, budgets, transactions, receipts, and local spending insight using Room-backed storage.",
    tags: ["Kotlin", "Room", "Finance", "Offline-first"],
    links: [
      { label: "Google Play", href: "https://play.google.com/store/apps/details?id=com.michael.insightlyspend" },
      { label: "GitHub", href: "https://github.com/michaelsam94/InsightlySpend" },
    ],
    media: {
      type: "terminal",
      terminalLines: ["wallets.local: synced", "budgets: tracked", "receipts: vaulted", "network: optional"],
    },
    highlight: true,
    year: "2025",
  },
  {
    id: "devpocket",
    title: "DevPocket",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline Android developer toolbox with code workspace, formatters, regex playground, local JS/math sandbox, and reference docs.",
    tags: ["Kotlin", "Developer Tools", "Room", "Offline-first"],
    links: [
      { label: "Google Play", href: "https://play.google.com/store/apps/details?id=com.michael.devpocket" },
      { label: "GitHub", href: "https://github.com/michaelsam94/DevPocket" },
    ],
    media: {
      type: "terminal",
      terminalLines: ["workspace.local: ready", "format.json: ok", "regex.tests: passing", "network: none"],
    },
    year: "2025",
  },
  {
    id: "vscode-extensions",
    title: "VS Code Extension Suite",
    company: "MichaelSam94",
    description:
      "Document and workspace extensions for CSV, PDF, DOCX, Markdown, conversion workflows, and AI context handoff across Marketplace and Open VSX.",
    tags: ["TypeScript", "VS Code API", "Open VSX"],
    links: [
      { label: "Marketplace", href: profile.vscodeMarketplace },
      { label: "Open VSX", href: profile.openVsx },
    ],
    media: {
      type: "terminal",
      terminalLines: ["publisher: MichaelSam94", "extensions: 9", "surfaces: marketplace/open-vsx", "runtime: node"],
    },
    year: "2026",
  },
  {
    id: "privai",
    title: "PrivAI",
    company: "MichaelSam94 · Google Play",
    description:
      "Privacy-first workspace for notes, voice transcripts, OCR extracts, and on-device summaries without cloud uploads.",
    tags: ["Kotlin", "On-device AI", "OCR", "Privacy"],
    links: [
      { label: "Google Play", href: "https://play.google.com/store/apps/details?id=com.michael.privai" },
      { label: "GitHub", href: "https://github.com/michaelsam94/PrivAI" },
    ],
    media: {
      type: "terminal",
      terminalLines: ["cloud.uploads: disabled", "ocr.local: enabled", "summary.model: device", "privacy: first"],
    },
    year: "2025",
  },
  {
    id: "doworkss",
    title: "Doworkss Service Marketplace",
    company: "Mazaady",
    description:
      "Jetpack Compose service marketplace across 240+ categories, delivered as an MVP with a two-engineer Android team in under three months.",
    tags: ["Compose", "MVVM", "Clean Architecture"],
    links: [{ label: "Play listing", href: "https://play.google.com/store/apps/details?id=com.doworkss" }],
    media: {
      type: "terminal",
      terminalLines: ["categories: 240+", "team.android: 2", "mvp: <3 months", "installs: 100k+"],
    },
    year: "2022",
  },
];

export const experienceData: ExperienceData[] = [
  {
    company: "Tadafuq",
    role: "Tech Lead",
    period: { start: "Jun 2024", end: "Present" },
    isCurrent: true,
    bullets: [
      "Architected EV charging management platform across Python/OCPP v1.6, Node.js WebSocket services, and Flutter apps.",
      "Led a cross-functional team of six while keeping architecture decisions and delivery quality visible.",
      "Designed P2P local-network remote control with sub-100ms sync and zero critical post-launch defects.",
    ],
  },
  {
    company: "Communico",
    role: "Senior Android Developer",
    period: { start: "Jun 2023", end: "Jun 2024" },
    isCurrent: false,
    bullets: [
      "Built Android apps for CRUZR and Pepper humanoid robots deployed at NEOM City.",
      "Integrated GPT-4 intent recognition, STT/TTS, robot SDK modules, and touchscreen flows.",
      "Reduced human escalations by 35% and supported 99%+ uptime in live environments.",
    ],
  },
  {
    company: "Mazaady",
    role: "Senior Android Developer",
    period: { start: "Jun 2022", end: "Jun 2023" },
    isCurrent: false,
    bullets: [
      "Led Android delivery for Doworkss and live-auction commerce products with Jetpack Compose and MVVM.",
      "Integrated ExoPlayer and WebRTC for 120k+ MAU live auction workflows.",
      "Improved engagement by 20% and kept ANR below 0.1% through production performance work.",
    ],
  },
  {
    company: "Rowaad",
    role: "Senior Android Developer",
    period: { start: "Sep 2020", end: "May 2022" },
    isCurrent: false,
    bullets: [
      "Led four Android engineers and introduced code review standards that improved release quality.",
      "Migrated 15+ modules to MVVM and Clean Architecture with coroutines and Firebase.",
      "Maintained 99.9% crash-free releases and raised unit coverage around critical flows.",
    ],
  },
  {
    company: "Ready Apps",
    role: "Mobile Developer",
    period: { start: "Apr 2018", end: "Aug 2020" },
    isCurrent: false,
    bullets: [
      "Built Firebase and Google Maps pharmacy locator workflows for 50k+ users and 100+ branches.",
      "Shipped inventory and sales apps across 100+ locations with practical field constraints.",
    ],
  },
];

export const contactLinks = [
  { label: "LinkedIn", href: profile.linkedin },
  { label: "GitHub", href: profile.github },
{ label: "Play Store", href: profile.playStoreDeveloper },
{ label: "VS Code Marketplace", href: profile.vscodeMarketplace },
{ label: "Open VSX", href: profile.openVsx },
{ label: "Download CV", href: profile.cvUrl },
] as const;

export const portfolioFaq = [
  {
    question: "What roles does Michael Samuel Naeem focus on?",
    answer:
      "He focuses on senior Android, staff Android, mobile architect, Flutter, and technical lead roles where delivery and architecture both matter.",
  },
  {
    question: "Where is he based, and does he work remotely?",
    answer:
      "He is based in Cairo, Egypt and works with remote teams across Europe, the United States, and other global markets.",
  },
  {
    question: "What domains has he shipped in?",
    answer:
      "His production work spans humanoid robotics, EV charging IoT, real-time live auctions, fintech wallets, e-commerce, Android TV, and developer tools.",
  },
  {
    question: "How can recruiters contact him?",
    answer: `Email ${profile.email}, use LinkedIn, or download the CV linked from the portfolio.`,
  },
] as const;

export const workSlug = (name: string): string =>
  name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

export type Project =
  | {
      name: string;
      company: string;
      description: string;
      tags: string[];
      highlight?: boolean;
      link: string;
    }
  | {
      name: string;
      company: string;
      description: string;
      tags: string[];
      highlight?: boolean;
      links: { label: string; href: string }[];
    };

export const projects: Project[] = projectsData.map((project) => ({
  name: project.title,
  company: project.company,
  description: project.description,
  tags: project.tags,
  highlight: project.highlight,
  links: project.links,
}));

export const experience = experienceData.map((job) => ({
  company: job.company,
  role: job.role,
  period: `${job.period.start} - ${job.period.end}`,
  location: job.isCurrent ? "Cairo · On-site" : "Remote / Hybrid",
  description: job.bullets.join(" "),
  tags: [],
  icon: job.isCurrent ? ">" : "-",
}));

export const vscodeExtensions = [
  { slug: "csv-studio", name: "CSV Studio", description: "View and edit CSV files as interactive spreadsheets in VS Code." },
  { slug: "contextporterext", name: "Context Porter", description: "Export AI session and project context to Markdown for handoff." },
  { slug: "pdfviewerext", name: "PdfViewer", description: "Open PDF files quickly from VS Code." },
  { slug: "pdftomdext", name: "PdfToMd", description: "Convert PDF files to Markdown from VS Code." },
  { slug: "mdviewerext", name: "MdViewer", description: "Preview Markdown files quickly from VS Code." },
  { slug: "mdtopdfext", name: "MdToPdf", description: "Convert Markdown files to PDF from VS Code." },
  { slug: "docxviewerext", name: "DocxViewer", description: "Preview DOCX files quickly from VS Code." },
  { slug: "docxtopdfext", name: "DocxToPdf", description: "Convert DOCX files to PDF from VS Code." },
  { slug: "docxtomdext", name: "DocxToMd", description: "Convert DOCX files to Markdown from VS Code." },
] as const;

export const playStoreApps = projectsData
  .filter((project) => project.company.includes("Google Play"))
  .map((project) => ({
    name: project.title,
    packageId: project.links[0]?.href.split("id=")[1] ?? "",
    playStoreUrl: project.links[0]?.href ?? "",
    image: "/og-image.png",
    category: project.tags[0] ?? "Android",
    description: project.description,
  }));
