import type { Metadata } from "next";
import NategaLanding from "./NategaLanding";
import "./natega.css";

export const metadata: Metadata = {
  title: "نتيجة الثانوية العامة 2026 بالاسم ورقم الجلوس",
  description: "نتيجة الثانوية العامة 2026 نظام حديث بالاسم أو رقم الجلوس. اعرف المجموع من 320 والنسبة المئوية وحالة الطالب فوراً.",
  keywords: ["نتيجة الثانوية العامة", "نتيجة الثانوية العامة 2026", "نتيجة الثانوية العامة بالاسم", "نتيجة الثانوية العامة برقم الجلوس", "نتيجة ثانوية عامة نظام حديث", "مجموع الثانوية العامة", "نسبة الثانوية العامة", "Natega"],
  alternates: {
    canonical: "/natega/",
    languages: { ar: "/natega/", en: "/en/natega/", "en-EG": "/franko/natega/", "x-default": "/natega/" },
  },
  openGraph: {
    title: "نتيجة الثانوية العامة 2026 بالاسم ورقم الجلوس",
    description: "ابحث في نتيجة الثانوية العامة واعرف المجموع والنسبة المئوية فوراً.",
    url: "/natega/",
    locale: "ar_EG",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "نتيجة الثانوية العامة 2026 بالاسم ورقم الجلوس",
    description: "ابحث عن النتيجة واعرف المجموع من 320 والنسبة المئوية فوراً.",
  },
};

export default function NategaPage() {
  return <NategaLanding locale="ar" />;
}
