import type { Metadata } from "next";
import fs from "node:fs";
import path from "node:path";
import NategaSearch from "./NategaSearch";
import "./natega.css";

type Manifest = {
  count: number;
  nameShards: Record<string, string>;
  seatPrefixes: string[];
};

export const metadata: Metadata = {
  title: "نتيجة الثانوية العامة | Natega",
  description: "ابحث عن نتيجة الثانوية العامة بالاسم أو رقم الجلوس.",
};

function getManifest(): Manifest {
  const file = path.join(process.cwd(), "public", "natega-data", "manifest.json");
  return JSON.parse(fs.readFileSync(file, "utf8")) as Manifest;
}

export default function NategaPage() {
  const manifest = getManifest();

  return (
    <main className="natega-page" dir="rtl">
      <section className="natega-shell">
        <div className="natega-kicker">نتيجة الثانوية العامة · نظام حديث</div>
        <h1>اعرف نتيجتك</h1>
        <p className="natega-intro">
          ابحث بسهولة باستخدام اسم الطالب أو رقم الجلوس، وستظهر النتيجة مباشرة.
        </p>
        <NategaSearch manifest={manifest} />
      </section>
    </main>
  );
}
