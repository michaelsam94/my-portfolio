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
