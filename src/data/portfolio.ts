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
  heroAvatar: "/profile-photo-hero.webp",
  headline:
    "Android engineer and architect with 10+ years shipping production mobile software—Kotlin, Jetpack Compose, and Flutter—for robotics, EV infrastructure, fintech, and real-time streaming.",
  /** Descriptive alt text for the hero image (SEO & accessibility). */
  avatarAlt:
    "Michael Samuel Naeem — senior Android developer and tech lead based in Cairo, Egypt.",
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
  {
    question: "Does Michael Samuel Naeem match Arabic searches for Android developers?",
    answer:
      "Yes. He is an Android developer in Cairo, Egypt: مطور أندرويد أول، مهندس تطبيقات موبايل، مطور Kotlin، ومطور Flutter available for remote English-speaking teams first, with Arabic search visibility as a secondary target.",
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
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.insightlyspend",
    image: "https://play-lh.googleusercontent.com/rV8uofctlrtogubdeGCxkAaSb9zFRT8Sh61ihe5qtvC0Kmledu9xhlnFdZAev3DTVQ8PEqni0aTU5nAM_ST-",
    category: "Finance",
    description: "Personal finance and spending insight tool for tracking money habits with clarity.",
  },
  {
    name: "Tic Tac Toe",
    packageId: "com.michael.tic_tac_toe",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.tic_tac_toe",
    image: "https://play-lh.googleusercontent.com/vQXAyB1FaRE0ViZVg4yjVVw7J6F4HljEyS8lvfeZ3YXVgh3riPrrFMpQWXgiXQswL7TeSR4yiuHyGoqL2RPIDDI",
    category: "Game",
    description: "A clean, lightweight classic Tic Tac Toe game built for quick play sessions.",
  },
  {
    name: "Subtrackr",
    packageId: "com.aistudio.subtrackr",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.aistudio.subtrackr",
    image: "https://play-lh.googleusercontent.com/U-P2L_vRJZ0pIPrj_iUG01Tt8rvZUii3ys8UO_Zonz1Fo7Rf3y5dHy8gMK6wq8cxN7RfBJ5cVQmFP-SFZCcG",
    category: "Finance",
    description: "Subscription tracker for monitoring recurring payments and keeping monthly costs visible.",
  },
  {
    name: "WalkPlanner",
    packageId: "com.michael.walkplanner",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.walkplanner",
    image: "https://play-lh.googleusercontent.com/ANH6OVzyeLAYijwXb8qR92t398xXNzAZDySDRvOCcq5pBuOUr2LvhJpzJs7LrA1JnRk11uBChS4_IrTv55XqlA",
    category: "Health",
    description: "Walking route and daily movement planner for simple personal activity routines.",
  },
  {
    name: "AuraSound",
    packageId: "com.michael.aurasound",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.aurasound",
    image: "https://play-lh.googleusercontent.com/mj1DJLB3vLygQw9rGBatKOSWCUy3XbdxaQM2ZV_F86uAqrVLxtR8v1WrwH0qWB54h4xZT-hilBT2-pmPKTvoAA",
    category: "Audio",
    description: "Audio utility app for focused playback, sound control, and everyday listening workflows.",
  },
  {
    name: "Wi-Fi Drop",
    packageId: "com.michael.wifidrop",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.wifidrop",
    image: "https://play-lh.googleusercontent.com/WR7vIT2bkXYUVFpWg-ATiFxEsBznNsoBS-qryrs00VG-QQG0lx6_6pnuYkf1kzB-MPAfSf3o_0aYbkukRZBT",
    category: "Utility",
    description: "Wi-Fi sharing and transfer companion designed for fast local connectivity workflows.",
  },
  {
    name: "Todo App",
    packageId: "com.michael.todoapps",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.todoapps",
    image: "https://play-lh.googleusercontent.com/nrrO8i3bLomhAwCsumivGhEtrvoEkEsyvIu6LvEeKnKvcVUllLh4BA0UWAc8Q3kq5zwnt8Xi0V1QhS5ZRyVu",
    category: "Productivity",
    description: "Simple task management app for capturing, organizing, and completing daily work.",
  },
  {
    name: "NotchCommand",
    packageId: "com.michael.notchcommand",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.notchcommand",
    image: "https://play-lh.googleusercontent.com/NZjwlbUzfrTHEsnF9wXme9zJxqzf7T_R0Zsp8RZxfuQ1dw8u8hcXCwMyFASvseG79JxIVMOtsihcDnhafylXrA",
    category: "Utility",
    description: "Device utility that turns screen notch space into a fast command surface.",
  },
  {
    name: "ClipVault",
    packageId: "com.michael.clipvault",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.clipvault",
    image: "https://play-lh.googleusercontent.com/DElpWkJTkHjkgQTnYJaYxKzlEBvFBfxjmSXoGq1c6mqa2IfguDKsiWK90ntmyvSYwdEOFlDPFkMIXC3_AnCNEA",
    category: "Productivity",
    description: "Clipboard manager for keeping copied text organized, searchable, and ready to reuse.",
  },
  {
    name: "FrozenDroid",
    packageId: "com.michael.frozendroid",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.frozendroid",
    image: "https://play-lh.googleusercontent.com/IoCfKm-tSHOo1qxbrLrZV_TVsMXVxu2i97ZZae48XN1rO7Ea6BVtqhVaEQR_BYhrkEnNG_7JK7WAd9pY6sfWFw",
    category: "Utility",
    description: "Android utility focused on app/device control and cleaner performance routines.",
  },
  {
    name: "PDF Toolkit",
    packageId: "com.michael.pdftoolkit",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.pdftoolkit",
    image: "https://play-lh.googleusercontent.com/ooKhHiR-q_fS7luJcQXETk-tr0HlHSm5x-IsuXu65CvaE8my1FbIEbmX0UCNYduWB0y4kleaqo2PcTV-MEyrgA",
    category: "Document",
    description: "Portable PDF tools for common document actions and lightweight file workflows.",
  },
  {
    name: "Bulk QR & Barcode Suite",
    packageId: "com.michael.bulkqrscanner",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.bulkqrscanner",
    image: "https://play-lh.googleusercontent.com/Vzzu81LLS7O0T5RIJ70QVu2LASUzEHd6YVud3UUFC1Fcjdcex1vV49tJx9U4Em52c3voZ6Y6TBRx7PO4dxVLJg",
    category: "Scanner",
    description: "Bulk QR and barcode scanning toolkit for batches, inventory, and everyday code capture.",
  },
  {
    name: "SensorScope",
    packageId: "com.michael.sensorscope",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.sensorscope",
    image: "https://play-lh.googleusercontent.com/4Fo2z_LzWTP-RBNQIx0L_Bu935uyG8IYtA5Z45B0P9QHHvZ72h5OsaOSYmKeAQTO03n6pTvE4Fk44uJPIXjC0Zk",
    category: "Developer",
    description: "Sensor dashboard for exploring live Android device sensor readings and diagnostics.",
  },
  {
    name: "Doc Scanner Vectorizer",
    packageId: "com.michael.docscannervectorizer",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.docscannervectorizer",
    image: "https://play-lh.googleusercontent.com/XQI8MGScBd3x0KypFyeilCmgcVZ8u9ikG9xIdxMjmDcyfgobnZPUpUHV8rmk-Jmyw2t33mILKfjokrbsfHb9cA",
    category: "Document",
    description: "Document scanner and vectorizer for turning paper captures into cleaner digital assets.",
  },
  {
    name: "FolderFlow",
    packageId: "com.michael.folderflow",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.folderflow",
    image: "https://play-lh.googleusercontent.com/dT3tvyTsYiDNXI-GYMHkesFaRz_5jHQ5soHsyv62EntTYbJLk49OMEjGdcDiAmBOS8noea9SiffYSe97Bl9OLA",
    category: "Productivity",
    description: "File and folder organization utility for tidier local storage workflows.",
  },
  {
    name: "Micro Budgeting",
    packageId: "com.michael.microbudgeting",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.microbudgeting",
    image: "https://play-lh.googleusercontent.com/8LLJaE7oILJduEYlilZmwoINxnrrFyUTITDdRsNk6MspnGcFyJPeM9_zE5hKbuxrMsKF4EbS0suMYs4Yc76V",
    category: "Finance",
    description: "Small-budget planning app for tracking micro expenses and short financial goals.",
  },
  {
    name: "StoreClear",
    packageId: "com.michael.storeclear",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.storeclear",
    image: "https://play-lh.googleusercontent.com/Qfy6nCkhx3-hdST19FP7NrSU5VcMXMVR40lFIeJcek2ZOnbQKpumm7txhM-NDhUurBxBesXbuhDAHXaV1CVd",
    category: "Utility",
    description: "Storage cleaning utility for clearing clutter and keeping Android space manageable.",
  },
  {
    name: "Smooth-Mo",
    packageId: "com.michael.smoothmo",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.smoothmo",
    image: "https://play-lh.googleusercontent.com/7vwn0tvOllRw2YhmPAccj8VM1nC4wJ7GWfe-hMGciaA6ktaSStobHetrttfNX376pvg3kq5j75o1DCzhBX7AgQ",
    category: "Utility",
    description: "Motion and smoothness utility for tuning or exploring Android device behavior.",
  },
  {
    name: "EdgeFlow",
    packageId: "com.michael.edgeflow",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.edgeflow",
    image: "https://play-lh.googleusercontent.com/sr97xuvu3ACSIZ3ZGBy1CH5ozS0TIoZ8x97NWIIzjl8NwE1fxBefCNXuOJHiEitx4beHGioS47oDUNhAFP8G8A",
    category: "Utility",
    description: "Edge gesture and shortcut utility designed for faster mobile navigation.",
  },
  {
    name: "PrivAI",
    packageId: "com.michael.privai",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.privai",
    image: "https://play-lh.googleusercontent.com/5sn9vK54oe59VJBs6ELVoyo6U7J8K-P3-42f7XmeMMToP6b8dGM-fP0wJaJ26HUb7nB2F8lk-80gYsb_cjTK6-s",
    category: "AI",
    description: "Privacy-focused AI utility for local-first, safer everyday assistance workflows.",
  },
  {
    name: "Photo Optimizer",
    packageId: "com.michael.photo.optimizer",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.photo.optimizer",
    image: "https://play-lh.googleusercontent.com/X8prc76-bR0nI8-pxxinWNqE_hW9YLJZjuFbE_gxn5PPdczgrVs7x0VfN0kCiJyXmFJfb7UocXRFPlRq19oYIw",
    category: "Media",
    description: "Photo compression and optimization tool for reducing image size while preserving quality.",
  },
  {
    name: "BLE Finder",
    packageId: "com.michael.blefinder",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.blefinder",
    image: "https://play-lh.googleusercontent.com/J7JKnuE6S8AatKuyMXl5O5cCsrY7oU7y2FtUmC-Xv-8bIk54aB3dlX4Fs8O94A_uN7B0poRjcrIQC_TUaxbdgew",
    category: "Developer",
    description: "Bluetooth Low Energy scanner for finding nearby devices and inspecting signals.",
  },
  {
    name: "ClearVoice AI",
    packageId: "com.michael.clearvoiceai",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.clearvoiceai",
    image: "https://play-lh.googleusercontent.com/UKTM7YeY9UEuDe4xFL1bcmK3bikq42_VuD6vzggsy4lRBz0GddVWdtwryHCiUyg2LQGkKHthvu5i7B5kdnxPGA",
    category: "AI",
    description: "AI voice cleanup tool for clearer recordings and improved spoken audio.",
  },
  {
    name: "DevPocket",
    packageId: "com.michael.devpocket",
    playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.devpocket",
    image: "https://play-lh.googleusercontent.com/lcTbR-DGu6SblFhlF55jL_Edw99GKjx5cfcpCmmq0FyR8yYsD71zIYeTNFo-BbkV8LhbumbapwyNOeig83VIdjo",
    category: "Developer",
    description: "Pocket developer toolkit with small utilities for mobile engineering workflows.",
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
