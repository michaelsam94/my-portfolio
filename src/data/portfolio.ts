export const profile = {
  name: "Michael Samuel Naeem",
  title: "Senior / Staff Android Engineer · Mobile Architect",
  tagline: "EV Infrastructure · Robotics · Real-Time Systems",
  location: "Cairo, Egypt",
  email: "michaelsam00@yahoo.com",
  phone: "+20 109 800 2198",
  linkedin: "https://www.linkedin.com/in/michaelsam00/",
  github: "https://github.com/michaelsam94",
  /** Tech blog — technology trends and engineering notes. */
  techBlog: "https://codeandcoffe.netlify.app/",
  vscodeMarketplace: "https://marketplace.visualstudio.com/publishers/MichaelSam94",
  openVsx: "https://open-vsx.org/namespace/michaelsam94",
  /** Google Play developer catalog (published apps under developer id MichaelSam94). */
  playStoreDeveloper: "https://play.google.com/store/apps/developer?id=MichaelSam94",
  cvUrl: "/Michael_Samuel_Naeem_Mobile_Developer_CV.pdf",
  avatar: "/profile-photo.png",
  /** Lighter square image for the hero (LCP); full `avatar` remains for OG / consistency elsewhere. */
  heroAvatar: "/profile-photo-hero.jpg",
  headline:
    "Android engineer and architect with 10+ years shipping production mobile software—Kotlin, Jetpack Compose, and Flutter—for robotics, EV infrastructure, fintech, and real-time streaming.",
  /** Descriptive alt text for the hero image (SEO & accessibility). */
  avatarAlt:
    "Michael Samuel Naeem — senior Android developer, mobile software engineer, technical lead, and staff-level architect. Professional portfolio photo, Cairo, Egypt.",
};

export const about = {
  summary:
    "I'm Michael Samuel Naeem — a senior Android developer, mobile engineer, software engineer, and technical lead with 10+ years of experience (staff-level mobile architect). I architect and ship Android and cross-platform solutions at scale, including lead Android developer responsibilities across squads. I led the Android platform for NEOM City's humanoid robotics deployment, built a full-stack EV Charging Management Platform, and delivered apps serving 120k+ MAU. I'm passionate about Clean Architecture, Kotlin, Jetpack Compose, and emerging tech—blockchain, Web3, and AI integration. I'm based in Cairo, Egypt, and I'm open to remote collaboration with teams across Europe, the United States, and worldwide.",
  highlights: [
    "Architected Android platform for NEOM City humanoid robots (CRUZR, Pepper)",
    "Full-stack EV Charging Platform: Python/OCPP, Node.js WebSocket, Flutter",
    "120k+ MAU live auction app with WebRTC; 99.9% crash-free production builds",
    "Led teams of 4–6; defined ADRs and reduced cross-team integration issues by ~40%",
    "VS Code extensions published on the Visual Studio Marketplace and Open VSX",
    "Google Play developer catalog (MichaelSam94): apps on the Play Store",
  ],
};

/**
 * Shown in About and mirrored as FAQPage JSON-LD (`StructuredData`).
 * Keep question/answer text aligned with what is visible on the page.
 */
export const portfolioFaq = [
  {
    question: "What roles does Michael Samuel Naeem focus on?",
    answer:
      "He works as a senior Android developer, staff Android engineer, mobile developer, software engineer, technical lead (tech lead), mobile architect, and Flutter developer—leading delivery end-to-end while staying hands-on with Kotlin, Jetpack Compose, and Flutter.",
  },
  {
    question: "Where is he based, and does he work remotely?",
    answer:
      "He is based in Cairo, Egypt, and collaborates with teams globally. He is open to remote roles with companies in Europe, the United States, and other regions, as well as hybrid arrangements when travel is required.",
  },
  {
    question: "What domains and platforms has he shipped?",
    answer:
      "Production work spans humanoid robotics (NEOM), EV charging and IoT (OCPP, WebSocket, Flutter), live auctions and streaming at scale (120k+ MAU), fintech and e-wallets, e-commerce, and Android TV—typically on MVVM or Clean Architecture with strong quality bars.",
  },
  {
    question: "How can recruiters or hiring managers contact him?",
    answer:
      "Use the contact section on this portfolio, reach out on LinkedIn (michaelsam00), or email michaelsam00@yahoo.com. A downloadable CV is linked from the hero section.",
  },
] as const;

export const experience = [
  {
    company: "Tadafuq",
    role: "Tech Lead",
    period: "Jun 2024 – Present",
    location: "Cairo · On-site",
    description:
      "Architected full-stack EV Charging Management Platform (Python/OCPP v1.6, Node.js WebSocket, Flutter). Led cross-functional team of 6. Designed P2P local-network remote control with sub-100ms latency. Shipped with zero critical post-launch defects.",
    tags: ["Flutter", "OCPP", "WebSocket", "IoT", "Python", "Node.js"],
    icon: "⚡",
  },
  {
    company: "Communico",
    role: "Senior Android Developer",
    period: "Jun 2023 – Jun 2024",
    location: "Remote",
    description:
      "Built Android apps for CRUZR and Pepper humanoid robots at NEOM City. Integrated GPT-4 for intent recognition; 35% reduction in human escalations. End-to-end STT/TTS and touchscreen interfaces; 99%+ uptime.",
    tags: ["Kotlin", "Robot SDK", "OpenAI", "STT/TTS", "NEOM"],
    icon: "🤖",
  },
  {
    company: "Mazaady",
    role: "Senior Android Developer",
    period: "Jun 2022 – Jun 2023",
    location: "Remote",
    description:
      "Led Android for Doworkss (240+ categories, Jetpack Compose, MVVM). Live auction platform with ExoPlayer + WebRTC for 120k+ MAU; 20% engagement increase. 15% performance gain, ANR below 0.1%.",
    tags: ["Jetpack Compose", "WebRTC", "ExoPlayer", "MVVM"],
    icon: "🎯",
  },
  {
    company: "Rowaad",
    role: "Senior Android Developer",
    period: "Sep 2020 – May 2022",
    location: "Cairo · Hybrid",
    description:
      "Led 4 Android engineers; introduced code review standards (30% quality improvement). Migrated 15+ modules to MVVM + Clean Architecture. 99.9% crash-free rate; ~70% unit test coverage.",
    tags: ["Clean Architecture", "TDD", "Coroutines", "Firebase"],
    icon: "📐",
  },
  {
    company: "Ready Apps",
    role: "Mobile Developer",
    period: "Apr 2018 – Aug 2020",
    location: "Cairo · On-site",
    description:
      "Firebase + Google Maps pharmacy locator for 50k+ users, 100+ branches; 50% search time reduction. Inventory and sales apps for 100+ locations.",
    tags: ["Firebase", "Google Maps", "Android"],
    icon: "📍",
  },
  {
    company: "EME International",
    role: "Android Developer",
    period: "Oct 2017 – Mar 2018",
    location: "Cairo · On-site",
    description:
      "Bus reservation for myFawry eWallet (10k+ monthly transactions), POS hardware, multi-flavor banking apps.",
    tags: ["eWallet", "POS", "Banking"],
    icon: "💳",
  },
  {
    company: "Pan Arab Media",
    role: "Android Developer",
    period: "Sep 2016 – Sep 2017",
    location: "Cairo · On-site",
    description:
      "E-commerce app (catalog, cart, checkout). Android TV client with Leanback for video platform.",
    tags: ["E-commerce", "Android TV", "Leanback"],
    icon: "📺",
  },
];

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

export const projects: Project[] = [
  {
    name: "InsightlySpend",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline-first Android personal finance app for wallets, budgets, transactions, receipts, and local insights using Room-backed storage.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.insightlyspend",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/InsightlySpend" },
    ],
    tags: ["Kotlin", "Room", "Finance", "Offline-first"],
    highlight: true,
  },
  {
    name: "SubTrackr",
    company: "MichaelSam94 · Google Play",
    description:
      "Subscription and license manager with renewal tracking, spending analytics, cancellation workflows, and AI-assisted portfolio insights.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.aistudio.subtrackr",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/SubtrackrAnroid" },
    ],
    tags: ["Kotlin", "AI", "Analytics", "Subscriptions"],
    highlight: true,
  },
  {
    name: "PrivAI",
    company: "MichaelSam94 · Google Play",
    description:
      "Privacy-first workspace for notes, voice transcripts, OCR extracts, and on-device summaries without cloud uploads.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.privai",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/PrivAI" },
    ],
    tags: ["Kotlin", "On-device AI", "OCR", "Privacy"],
    highlight: true,
  },
  {
    name: "DevPocket",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline Android developer toolbox with a code workspace, formatters, regex playground, local JS/math sandbox, and reference docs.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.devpocket",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/DevPocket" },
    ],
    tags: ["Kotlin", "Developer Tools", "Room", "Offline-first"],
    highlight: true,
  },
  {
    name: "EV Charging Management Platform · Mega Plug",
    company: "Tadafuq",
    description:
      "Full-stack EV charging: Python/OCPP v1.6 CMS, Node.js WebSocket middleware, Flutter app. P2P LAN control with sub-100ms sync. Consumer app Mega Plug on Google Play and App Store.",
    link: "https://play.google.com/store/apps/details?id=com.mega.plug",
    tags: ["Flutter", "OCPP", "WebSocket", "IoT"],
    highlight: true,
  },
  {
    name: "NEOM City Humanoid Robotics",
    company: "Communico",
    description:
      "Android apps for CRUZR & Pepper robots; GPT-4 intent recognition, STT/TTS, 4+ SDK modules. Thousands of daily interactions.",
    link: "https://github.com/michaelsam94",
    tags: ["Kotlin", "Robot SDK", "OpenAI"],
    highlight: true,
  },
  {
    name: "Doworkss · Service Marketplace",
    company: "Mazaady",
    description:
      "240+ categories, Jetpack Compose, MVVM Clean Architecture. Delivered MVP with 2-engineer team in under 3 months. Live on Google Play (100K+ installs).",
    link: "https://play.google.com/store/apps/details?id=com.doworkss",
    tags: ["Compose", "MVVM", "Clean Architecture"],
    highlight: true,
  },
  {
    name: "Mazaady · Live Auction & Commerce",
    company: "Mazaady",
    description:
      "Real-time bidding with ExoPlayer + WebRTC; 120k+ MAU, 20% engagement increase. Play listing: auctions, live broadcast, 100K+ installs.",
    link: "https://play.google.com/store/apps/details?id=com.mazaady",
    tags: ["WebRTC", "ExoPlayer", "Real-time"],
  },
  {
    name: "VS Code Extensions",
    company: "MichaelSam94",
    description:
      "Extensions for Visual Studio Code: published on the Microsoft marketplace and the Open VSX Registry (TypeScript, VS Code Extension API).",
    links: [
      {
        label: "VS Code Marketplace",
        href: "https://marketplace.visualstudio.com/publishers/MichaelSam94",
      },
      { label: "Open VSX", href: "https://open-vsx.org/namespace/michaelsam94" },
    ],
    tags: ["VS Code Extension API", "TypeScript", "Open VSX"],
  },
  {
    name: "Shoply Flutter Storefront MVP",
    company: "GitHub",
    description:
      "Flutter eCommerce MVP with Shopify Storefront GraphQL for catalog/checkout and Supabase for auth and app-owned data.",
    link: "https://github.com/michaelsam94/shoply",
    tags: ["Flutter", "Riverpod", "GoRouter", "Shopify GraphQL", "Supabase"],
  },
  {
    name: "Intelligent Trading Bot",
    company: "GitHub",
    description: "Python-based trading bot project. Active development.",
    link: "https://github.com/michaelsam94/intelleigent-trading-bot",
    tags: ["Python", "Trading"],
  },
  {
    name: "System Design Academy",
    company: "GitHub",
    description: "System design newsletter and learning resources.",
    link: "https://github.com/michaelsam94/system-design-academy",
    tags: ["System Design"],
  },
  {
    name: "Pharmacy Locator & Management",
    company: "Ready Apps",
    description:
      "GPS pharmacy finder for 50k+ users, 100+ branches; 50% search time reduction.",
    link: "https://github.com/michaelsam94",
    tags: ["Firebase", "Google Maps"],
  },
  {
    name: "Android REST Client Template",
    company: "GitHub",
    description: "Template for Android OAuth REST Client.",
    link: "https://github.com/michaelsam94/android-rest-client-template",
    tags: ["Java", "Android", "OAuth"],
  },
  {
    name: "Tic Tac Toe",
    company: "MichaelSam94 · Google Play",
    description:
      "Classic offline two-player Tic Tac Toe with a clean 3x3 board, instant win/draw detection, and no sign-in requirement.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.tic_tac_toe",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/tic_tac_toe" },
    ],
    tags: ["Kotlin", "Game", "Offline"],
  },
  {
    name: "WalkPlanner",
    company: "MichaelSam94 · Google Play",
    description:
      "Route planner for circular walking and running loops with OpenStreetMap overlays, GPS session tracking, and saved history.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.walkplanner",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/TrailMate" },
    ],
    tags: ["Kotlin", "Maps", "GPS", "OpenStreetMap"],
  },
  {
    name: "Photo Optimizer",
    company: "MichaelSam94 · Google Play",
    description:
      "Local photo compression, duplicate cleanup, EXIF metadata wiping, and batch processing with WorkManager.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.photo.optimizer",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/Photo-Optimizer" },
    ],
    tags: ["Kotlin", "WorkManager", "Media", "Privacy"],
  },
  {
    name: "ClearVoice AI",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline speech enhancement tool with live loopback, batch audio processing, multiband DSP filters, and local noise isolation.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.clearvoiceai",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/ClearVoice-AI" },
    ],
    tags: ["Kotlin", "DSP", "Audio", "Offline AI"],
  },
  {
    name: "Todo App",
    company: "MichaelSam94 · Google Play",
    description:
      "Focused task manager with priorities, categories, due dates, search, filters, sorting, and local productivity stats.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.todoapps",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/TodoAppAiStudio" },
    ],
    tags: ["Kotlin", "Productivity", "Local DB"],
  },
  {
    name: "NotchCommand",
    company: "MichaelSam94 · Google Play",
    description:
      "Interactive camera-cutout utility ring for shortcuts, battery status, audio visualization, charging state, and RGB effects.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.notchcommand",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/NotchCommand" },
    ],
    tags: ["Kotlin", "Overlay", "Accessibility", "UI"],
  },
  {
    name: "Wi-Fi Drop",
    company: "MichaelSam94 · Google Play",
    description:
      "Local-network file transfer app for sending files, folders, and browser downloads over the same Wi-Fi without cloud uploads.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.wifidrop",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/Wi-Fi-Drop" },
    ],
    tags: ["Kotlin", "Networking", "P2P", "Privacy"],
  },
  {
    name: "PDF Toolkit",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline PDF utility for merging, splitting, signing, and converting Markdown notes into generated PDFs on-device.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.pdftoolkit",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/PDF-Toolkit" },
    ],
    tags: ["Kotlin", "PDF", "Documents", "Offline"],
  },
  {
    name: "Bulk QR & Barcode Suite",
    company: "MichaelSam94 · Google Play",
    description:
      "Offline barcode suite for continuous ML Kit scanning, batch sessions, CSV/XLSX export, and branded QR code generation.",
    links: [
      {
        label: "Google Play",
        href: "https://play.google.com/store/apps/details?id=com.michael.bulkqrscanner",
      },
      { label: "GitHub", href: "https://github.com/michaelsam94/Bulk-QR-Barcode-Suite" },
    ],
    tags: ["Kotlin", "ML Kit", "QR", "Barcode"],
  },
  {
    name: "Compose ToDo",
    company: "GitHub",
    description: "Jetpack Compose sample app.",
    link: "https://github.com/michaelsam94/Compose-ToDo",
    tags: ["Kotlin", "Compose"],
  },
];

/** Listing details aligned with Google Play / App Store (as of early 2026). */
export const playStoreApps = [
  {
    name: "InsightlySpend",
    packageId: "com.michael.insightlyspend",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.insightlyspend",
    repoUrl: "https://github.com/michaelsam94/InsightlySpend",
    developer: "MichaelSam94",
    category: "Finance",
    installs: "1+",
    contentRating: "Rated 3+",
    about:
      "Offline-first money manager for Android: wallets, budgets, transaction search, receipt vault, spending trends, category breakdowns, and on-device insights backed by local storage.",
    tags: ["Finance", "Room", "Budgets", "Receipts"],
  },
  {
    name: "Tic Tac Toe",
    packageId: "com.michael.tic_tac_toe",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.tic_tac_toe",
    repoUrl: "https://github.com/michaelsam94/tic_tac_toe",
    developer: "MichaelSam94",
    category: "Casual",
    installs: "1+",
    contentRating: "Rated 3+",
    about:
      "Classic offline two-player Tic Tac Toe with a clean 3x3 board, instant win and draw detection, one-tap reset, and no ads or sign-in requirement.",
    tags: ["Game", "Offline", "Kotlin"],
  },
  {
    name: "SubTrackr",
    packageId: "com.aistudio.subtrackr",
    storeUrl: "https://play.google.com/store/apps/details?id=com.aistudio.subtrackr",
    repoUrl: "https://github.com/michaelsam94/SubtrackrAnroid",
    developer: "MichaelSam94",
    category: "Finance",
    installs: "1+",
    contentRating: "Rated 3+",
    about:
      "Subscription and software-license manager with renewal forecasts, spending charts, cancellation checklists, CSV import, and AI-assisted optimization insights.",
    tags: ["Subscriptions", "AI", "Analytics"],
  },
  {
    name: "WalkPlanner",
    packageId: "com.michael.walkplanner",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.walkplanner",
    repoUrl: "https://github.com/michaelsam94/TrailMate",
    developer: "MichaelSam94",
    category: "Health & Fitness",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Walking and running loop planner with OpenStreetMap data, surface preferences, multiple route options, live GPS tracking, unit settings, and local session history.",
    tags: ["Maps", "GPS", "OpenStreetMap"],
  },
  {
    name: "Photo Optimizer",
    packageId: "com.michael.photo.optimizer",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.photo.optimizer",
    repoUrl: "https://github.com/michaelsam94/Photo-Optimizer",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Local photo library optimizer for batch WebP/JPEG/PNG compression, EXIF metadata wiping, duplicate detection, before/after previews, and background processing.",
    tags: ["Media", "EXIF", "WorkManager"],
  },
  {
    name: "ClearVoice AI",
    packageId: "com.michael.clearvoiceai",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.clearvoiceai",
    repoUrl: "https://github.com/michaelsam94/ClearVoice-AI",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "On-device speech enhancer with real-time loopback, waveform visualization, multiband DSP isolation, noise gates, and batch audio-file processing.",
    tags: ["Audio", "DSP", "Offline AI"],
  },
  {
    name: "Todo App",
    packageId: "com.michael.todoapps",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.todoapps",
    repoUrl: "https://github.com/michaelsam94/TodoAppAiStudio",
    developer: "MichaelSam94",
    category: "Productivity",
    installs: "1+",
    contentRating: "Rated 3+",
    about:
      "Private everyday task manager with categories, priority levels, due dates, smart filters, sorting, search, detailed task views, and weekly progress stats.",
    tags: ["Tasks", "Productivity", "Offline-first"],
  },
  {
    name: "NotchCommand",
    packageId: "com.michael.notchcommand",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.notchcommand",
    repoUrl: "https://github.com/michaelsam94/NotchCommand",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Camera-cutout command ring with configurable tap gestures, system shortcuts, battery sweep, charging indicator, audio visualizer, and RGB animation modes.",
    tags: ["Overlay", "Accessibility", "Visualizer"],
  },
  {
    name: "PrivAI",
    packageId: "com.michael.privai",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.privai",
    repoUrl: "https://github.com/michaelsam94/PrivAI",
    developer: "MichaelSam94",
    category: "Productivity",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Private AI workspace for local notes, voice transcription, OCR extraction, summaries, keyword highlights, and sentiment hints without cloud uploads.",
    tags: ["On-device AI", "OCR", "Notes"],
  },
  {
    name: "DevPocket",
    packageId: "com.michael.devpocket",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.devpocket",
    repoUrl: "https://github.com/michaelsam94/DevPocket",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Offline developer utility suite with syntax-highlighted code workspace, JSON/XML/HTML/CSS/SQL formatting, regex playground, local JavaScript and math sandbox, and reference docs stored locally.",
    tags: ["Developer Tools", "Formatter", "Regex", "Offline"],
  },
  {
    name: "Wi-Fi Drop",
    packageId: "com.michael.wifidrop",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.wifidrop",
    repoUrl: "https://github.com/michaelsam94/Wi-Fi-Drop",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Cloud-free local-network file transfer for photos, videos, documents, folders, nearby receivers, transfer history, and browser downloads through Web Share.",
    tags: ["Wi-Fi", "P2P", "File transfer"],
  },
  {
    name: "PDF Toolkit",
    packageId: "com.michael.pdftoolkit",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.pdftoolkit",
    repoUrl: "https://github.com/michaelsam94/PDF-Toolkit",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Privacy-first PDF app for merging documents, splitting by page range, drawing and stamping signatures, and converting Markdown into PDFs locally.",
    tags: ["PDF", "Documents", "Offline"],
  },
  {
    name: "Bulk QR & Barcode Suite",
    packageId: "com.michael.bulkqrscanner",
    storeUrl: "https://play.google.com/store/apps/details?id=com.michael.bulkqrscanner",
    repoUrl: "https://github.com/michaelsam94/Bulk-QR-Barcode-Suite",
    developer: "MichaelSam94",
    category: "Tools",
    installs: "0+",
    contentRating: "Rated 3+",
    about:
      "Offline barcode operations suite with continuous ML Kit scanning, duplicate detection, batch/session auditing, CSV/XLSX export, and branded QR generation.",
    tags: ["ML Kit", "Barcode", "QR", "Export"],
  },
  {
    name: "Mega Plug",
    packageId: "com.mega.plug",
    storeUrl: "https://play.google.com/store/apps/details?id=com.mega.plug",
    appStoreUrl: "https://apps.apple.com/eg/app/mega-plug/id6759159407",
    developer: "MEGA PLUG FOR VEHICLE CHARGING STATIONS",
    category: "Auto & Vehicles",
    installs: "10+",
    contentRating: "Everyone",
    iosCategory: "Business",
    iosRating: "5.0",
    iosRatingsCount: "2 ratings",
    about:
      "Complete EV charging companion: map of nearby stations with filters (location, availability, connector), QR start/stop, live session metrics via WebSocket, wallet and cards, RFID cards, charging history and PDF reports, multi-vehicle profiles, guest mode, offline maps for saved stations, push notifications, dark mode, and multi-language support.",
    tags: ["EV", "OCPP ecosystem", "WebSocket", "Maps", "Flutter"],
  },
  {
    name: "Mazaady",
    packageId: "com.mazaady",
    storeUrl: "https://play.google.com/store/apps/details?id=com.mazaady",
    developer: "mazaady portal",
    category: "Shopping",
    installs: "100K+",
    contentRating: "Everyone",
    about:
      "Marketplace for wholesalers, retailers, and individuals: 55+ classifications to buy and sell new or used products through auctions, with live video or audio broadcast. Online payment and shipping coming soon; reschedule auctions and sell to the next bidder without recreating listings.",
    tags: ["Auction", "Live stream", "E‑commerce"],
  },
  {
    name: "Doworkss",
    packageId: "com.doworkss",
    storeUrl: "https://play.google.com/store/apps/details?id=com.doworkss",
    developer: "mazaady portal",
    category: "Business",
    installs: "100K+",
    contentRating: "Teen",
    about:
      "Free service platform affiliated with Mazaady: post or request services across 240+ categories. One account can be provider, requester, or both; connect with others at no platform fee.",
    tags: ["Services", "Marketplace", "Mazaady"],
  },
  {
    name: "myfawry",
    packageId: "com.fawry.myfawry",
    storeUrl: "https://play.google.com/store/apps/details?id=com.fawry.myfawry",
    developer: "Fawry for Banking & Payment Technology Services",
    category: "Finance",
    installs: "10M+",
    rating: "3.7",
    reviewCount: "173K+",
    contentRating: "Everyone",
    about:
      "Bills, payments, and banking in one app—including yellowcard prepaid (with Banque Misr & Meeza), card vault, QuickPay for recurring bills, recharges, donations, loans, insurance, and partner discounts.",
    tags: ["Payments", "Wallet", "Banking"],
  },
  {
    name: "NBE PhoneCash",
    packageId: "com.emeint.android.mwallet",
    storeUrl: "https://play.google.com/store/apps/details?id=com.emeint.android.mwallet",
    developer: "National Bank of Egypt",
    category: "Finance",
    installs: "1M+",
    rating: "2.3",
    reviewCount: "28.8K+",
    contentRating: "Everyone",
    about:
      "NBE mobile wallet: load from NBE cards, ATM cash in/out (Meeza), instant transfers, scan-and-pay, virtual card for online purchases, branch/agent cash, bill payments, Aman Elmasryeen, and Tahya Masr donations.",
    tags: ["eWallet", "Meeza", "NBE"],
  },
  {
    name: "BM Wallet",
    packageId: "com.emeint.android.mwallet.bm",
    storeUrl: "https://play.google.com/store/apps/details?id=com.emeint.android.mwallet.bm",
    developer: "Banque Misr",
    category: "Finance",
    installs: "1M+",
    rating: "3.1",
    reviewCount: "14K+",
    contentRating: "Everyone",
    about:
      "Banque Misr wallet without needing a bank account: deposit/withdraw via agents, retailers, or 9,000+ ATMs; send/receive to any Egyptian wallet; link BM cards; pay mobile, utilities, syndicates, flights, and Fawry QR; favorites and dedicated support.",
    tags: ["eWallet", "Banque Misr", "Bills"],
  },
  {
    name: "CIB Smart Wallet",
    packageId: "paymob.cib.smartwallet",
    storeUrl: "https://play.google.com/store/apps/details?id=paymob.cib.smartwallet",
    developer: "CIB Egypt",
    category: "Finance",
    installs: "1M+",
    rating: "2.2",
    reviewCount: "7.14K+",
    contentRating: "Everyone",
    about:
      "CIB Smart Wallet (with Meeza Digital): send/receive between wallets, in-store QR purchases, virtual cards, airtime, deposit/withdraw at CIB agents and ATMs, link up to two CIB cards, bills, charities, favorites, and fee overview—no CIB account required to register.",
    tags: ["eWallet", "CIB", "QR pay"],
  },
  {
    name: "QNB Egypt E-Wallet",
    packageId: "com.emeint.android.mwallet.qnb",
    storeUrl: "https://play.google.com/store/apps/details?id=com.emeint.android.mwallet.qnb",
    developer: "QNB",
    category: "Finance",
    installs: "500K+",
    rating: "3.3",
    reviewCount: "6.13K+",
    contentRating: "Everyone",
    about:
      "QNB Egypt wallet: load from accounts, cards, retailers, or Meeza ATMs; mobile top-up; telecom, utility, traffic, and subscription payments; transfers; withdraw at agents/ATMs; QR purchases; favorites; nearest Fawry agents on map.",
    tags: ["eWallet", "QNB", "Meeza"],
  },
];

export const skills = {
  mobile: [
    "Kotlin",
    "Java",
    "Jetpack Compose",
    "Android SDK",
    "XML",
    "Material Design 3",
    "Android TV (Leanback)",
    "Flutter / Dart",
  ],
  architecture: [
    "Clean Architecture",
    "MVVM",
    "MVP",
    "SOLID",
    "Multi-module",
    "Domain-Driven Design",
  ],
  jetpack: [
    "ViewModel",
    "LiveData",
    "Room",
    "Navigation",
    "WorkManager",
    "DataStore",
    "Paging 3",
    "CameraX",
  ],
  async: ["Coroutines", "Flow", "RxJava", "Hilt", "Dagger 2", "Koin"],
  networking: [
    "Retrofit",
    "OkHttp",
    "GraphQL",
    "WebSocket",
    "REST",
    "gRPC",
    "OCPP v1.6",
  ],
  media: [
    "ExoPlayer",
    "WebRTC",
    "STT/TTS",
    "Robot SDKs",
    "Google Maps SDK",
  ],
  emerging: [
    "OpenAI API (GPT-4)",
    "Intent Recognition",
    "Blockchain",
    "Web3",
    "Smart Contracts",
  ],
  devops: [
    "Git",
    "GitHub",
    "Jenkins",
    "Gradle",
    "Play Store",
    "CI/CD",
    "JUnit",
    "Mockito",
    "Espresso",
  ],
  tooling: [
    "VS Code Extension API",
    "TypeScript",
    "Visual Studio Marketplace",
    "Open VSX",
  ],
} as const;

/** Every skill string once, sorted — used for SEO structured data and discovery. */
export const allSkillsFlat: readonly string[] = Array.from(
  new Set(Object.values(skills).flat() as string[]),
).sort((a, b) => a.localeCompare(b));

export const certifications = [
  { name: "Android Developer Nanodegree", org: "Udacity", year: "2017" },
  { name: "Mobile Application Launchpad", org: "MCIT & Google via Udacity", year: "2016" },
  { name: "Blockchain Fundamentals", org: "In Progress", year: "2025" },
  { name: "Flutter Essential Training", org: "LinkedIn Learning", year: "—" },
  { name: "iOS 17 Development Essential Training", org: "LinkedIn Learning", year: "—" },
];

export const impact = [
  { value: "10+", label: "Years Android engineering" },
  { value: "120k+", label: "MAU on live auction platform" },
  { value: "99.9%", label: "Crash-free rate (production)" },
  { value: "50%", label: "Search time reduction (pharmacy locator)" },
  { value: "35%", label: "Fewer human escalations (NEOM robots)" },
  { value: "6+", label: "Companies & domains" },
];
