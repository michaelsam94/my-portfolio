import type { Metadata } from "next";
import NategaLanding from "@/app/natega/NategaLanding";
import "@/app/natega/natega.css";

export const metadata: Metadata = {
  title: "Thanaweya Amma Results 2026 by Name or Seat Number",
  description: "Search Egypt Thanaweya Amma results 2026 by Arabic student name or seat number. View the score out of 320, percentage and result status.",
  keywords: ["Thanaweya Amma results 2026", "Egypt high school results", "Thanaweya Amma by name", "Thanaweya Amma seat number", "Natega Egypt", "نتيجة الثانوية العامة"],
  alternates: {
    canonical: "/en/natega/",
    languages: { ar: "/natega/", en: "/en/natega/", "en-EG": "/franko/natega/", "x-default": "/natega/" },
  },
  openGraph: {
    title: "Thanaweya Amma Results 2026 | Natega",
    description: "Search Egyptian high school results by name or seat number.",
    url: "/en/natega/",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Thanaweya Amma Results 2026 | Natega",
    description: "Search by student name or seat number and view the percentage instantly.",
  },
};

export default function EnglishNategaPage() {
  return <NategaLanding locale="en" />;
}
