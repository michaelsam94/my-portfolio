import type { Metadata } from "next";
import NategaLanding from "@/app/natega/NategaLanding";
import "@/app/natega/natega.css";

export const metadata: Metadata = {
  title: "Natiget Thanaweya Amma 2026 Bel Esm Aw Rakam El Geloos",
  description: "Dawar 3ala natiget el thanaweya el 3ama 2026 bel esm aw rakam el geloos. E3raf el magmo3 men 320, el percentage, w 7alet el taleb.",
  keywords: ["natiget thanaweya amma 2026", "natiga bel esm", "natiga rakam el geloos", "thanaweya amma franco", "natega egypt", "نتيجة الثانوية العامة"],
  alternates: {
    canonical: "/franko/natega/",
    languages: { ar: "/natega/", en: "/en/natega/", "en-EG": "/franko/natega/", "x-default": "/natega/" },
  },
  openGraph: {
    title: "Natiget Thanaweya Amma 2026 | Natega",
    description: "Dawar 3ala el natiga bel esm aw rakam el geloos.",
    url: "/franko/natega/",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Natiget Thanaweya Amma 2026 | Natega",
    description: "Dawar bel esm aw rakam el geloos w e3raf el percentage.",
  },
};

export default function FrankoNategaPage() {
  return <NategaLanding locale="franko" />;
}
