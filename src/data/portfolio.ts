export const profile = {
  name: "Michael Samuel Naeem",
  title: "Senior / Staff Android Engineer · Mobile Architect",
  tagline: "EV Infrastructure · Robotics · Real-Time Systems",
  location: "Cairo, Egypt",
  email: "michaelsam00@yahoo.com",
  phone: "+20 109 800 2198",
  linkedin: "https://www.linkedin.com/in/michaelsam00/",
  github: "https://github.com/michaelsam94",
  cvUrl: "/Michael_Samuel_Naeem_CV4.pdf", // Put your CV in public/ and name it or use full URL
  avatar: "https://avatars.githubusercontent.com/u/9461037?v=4",
  headline:
    "Android Engineer and Architect with 10+ years delivering production mobile systems across robotics, EV infrastructure, fintech, and real-time streaming.",
};

export const about = {
  summary:
    "I architect and ship Android & cross-platform solutions at scale. I led the Android platform for NEOM City's humanoid robotics deployment, built a full-stack EV Charging Management Platform, and delivered apps serving 120k+ MAU. I'm passionate about Clean Architecture, Kotlin, Jetpack Compose, and emerging tech—blockchain, Web3, and AI integration.",
  highlights: [
    "Architected Android platform for NEOM City humanoid robots (CRUZR, Pepper)",
    "Full-stack EV Charging Platform: Python/OCPP, Node.js WebSocket, Flutter",
    "120k+ MAU live auction app with WebRTC; 99.9% crash-free production builds",
    "Led teams of 4–6; defined ADRs and reduced cross-team integration issues by ~40%",
  ],
};

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

export const projects = [
  {
    name: "EV Charging Management Platform",
    company: "Tadafuq",
    description:
      "Full-stack EV charging: Python/OCPP v1.6 CMS, Node.js WebSocket middleware, Flutter app. P2P LAN control with sub-100ms sync.",
    link: "https://github.com/michaelsam94",
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
      "240+ categories, Jetpack Compose, MVVM Clean Architecture. Delivered MVP with 2-engineer team in under 3 months.",
    link: "https://github.com/michaelsam94",
    tags: ["Compose", "MVVM", "Clean Architecture"],
    highlight: true,
  },
  {
    name: "Mazaady Live Auction",
    company: "Mazaady",
    description:
      "Real-time bidding with ExoPlayer + WebRTC; 120k+ MAU, 20% engagement increase.",
    link: "https://github.com/michaelsam94",
    tags: ["WebRTC", "ExoPlayer", "Real-time"],
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
};

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
