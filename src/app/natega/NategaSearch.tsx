"use client";

import { FormEvent, useState } from "react";
import { Search, UserRound, Hash, LoaderCircle, AlertCircle } from "lucide-react";

type ResultRecord = [seat: string, name: string, total: string, status: string];
type Manifest = {
  count: number;
  nameShards: Record<string, string>;
  seatPrefixes: string[];
  scoreStats: Record<string, {
    rankWithRepetition: number;
    rankWithoutRepetition: number;
    sameScoreCount: number;
  }>;
};

const MAX_RESULTS = 25;
const MAX_TOTAL = 320;

type Locale = "ar" | "en" | "franko";

const copy = {
  ar: {
    label: "الاسم أو رقم الجلوس",
    placeholder: "مثال: أحمد محمد أو 2001970",
    search: "عرض النتيجة",
    searching: "جاري البحث",
    hint: "يمكنك البحث بالاسم الكامل أو جزء منه، أو إدخال رقم الجلوس بدقة.",
    emptyInput: "اكتب الاسم أو رقم الجلوس أولاً.",
    seatLength: "رقم الجلوس يجب أن يتكون من 3 أرقام على الأقل.",
    nameLength: "اكتب 3 أحرف على الأقل للبحث بالاسم.",
    failed: "تعذر البحث الآن. حاول مرة أخرى.",
    noResults: "لم نعثر على نتيجة مطابقة. راجع الاسم أو رقم الجلوس وحاول مرة أخرى.",
    result: "النتيجة",
    results: "نتيجة",
    first: "أول",
    student: "اسم الطالب",
    seat: "رقم الجلوس",
    total: "المجموع",
    percentage: "النسبة المئوية",
    rankWithRepetition: "الترتيب العام مكرر",
    rankWithoutRepetition: "الترتيب العام بدون تكرار",
    sameScoreCount: "عدد الطلاب بنفس المجموع",
    status: "الحالة",
    dataset: "قاعدة البيانات الحالية تشمل",
    students: "طالب وطالبة.",
  },
  en: {
    label: "Student name or seat number",
    placeholder: "Example: Ahmed Mohamed or 2001970",
    search: "Show result",
    searching: "Searching",
    hint: "Search using the full Arabic name, part of the name, or the exact seat number.",
    emptyInput: "Enter a student name or seat number first.",
    seatLength: "The seat number must contain at least 3 digits.",
    nameLength: "Enter at least 3 characters to search by name.",
    failed: "Search is temporarily unavailable. Please try again.",
    noResults: "No matching result was found. Check the name or seat number and try again.",
    result: "Search results",
    results: "result(s)",
    first: "First",
    student: "Student name",
    seat: "Seat number",
    total: "Total score",
    percentage: "Percentage",
    rankWithRepetition: "Overall rank with ties",
    rankWithoutRepetition: "Overall rank without gaps",
    sameScoreCount: "Students with the same score",
    status: "Status",
    dataset: "The current database contains",
    students: "students.",
  },
  franko: {
    label: "Esm el taleb aw rakam el geloos",
    placeholder: "Mesal: Ahmed Mohamed aw 2001970",
    search: "E3red el natiga",
    searching: "Benedawar",
    hint: "Momken tedawar bel esm el 3araby kamel, goz2 men el esm, aw rakam el geloos.",
    emptyInput: "Ekteb el esm aw rakam el geloos el awel.",
    seatLength: "Rakam el geloos lazm yeb2a 3 arkam 3al a2al.",
    nameLength: "Ekteb 3 7orof 3al a2al 3ashan tedawar bel esm.",
    failed: "El search msh sh8al delwa2ty. Garab tany.",
    noResults: "Mal2enash natiga motab2a. Rage3 el esm aw rakam el geloos.",
    result: "Natiget el search",
    results: "natiga",
    first: "Awal",
    student: "Esm el taleb",
    seat: "Rakam el geloos",
    total: "El magmo3",
    percentage: "El nesba el me2aweya",
    rankWithRepetition: "El tartib el 3am mokarar",
    rankWithoutRepetition: "El tartib el 3am mn 8er tekrar",
    sameScoreCount: "3adad el talaba benafs el magmo3",
    status: "El 7ala",
    dataset: "El database feha",
    students: "taleb w taleba.",
  },
} satisfies Record<Locale, Record<string, string>>;

function normalizeArabic(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u064b-\u065f\u0670\u06d6-\u06ed]/g, "")
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/ـ/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export default function NategaSearch({ manifest, locale = "ar" }: { manifest: Manifest; locale?: Locale }) {
  const t = copy[locale];
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResultRecord[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    setError("");
    setSearched(false);

    if (!value) {
      setError(t.emptyInput);
      return;
    }

    setLoading(true);
    try {
      const isSeatNumber = /^\d+$/.test(value);
      let matches: ResultRecord[] = [];

      if (isSeatNumber) {
        if (value.length < 3) {
          throw new Error(t.seatLength);
        }
        const response = await fetch(`/natega-data/seats/${value.slice(0, 3)}.json`);
        if (response.ok) {
          const records = (await response.json()) as ResultRecord[];
          matches = records.filter((record) => record[0] === value);
        }
      } else {
        const normalized = normalizeArabic(value);
        if (normalized.length < 3) {
          throw new Error(t.nameLength);
        }
        const shard = manifest.nameShards[normalized[0]];
        if (shard) {
          const response = await fetch(`/natega-data/names/${shard}.json`);
          if (response.ok) {
            const records = (await response.json()) as ResultRecord[];
            matches = records
              .filter((record) => normalizeArabic(record[1]).includes(normalized))
              .slice(0, MAX_RESULTS)
              .map(([seat, name, total, status]) => [seat, name, total, status]);
          }
        }
      }

      setResults(matches);
      setSearched(true);
    } catch (caught) {
      setResults([]);
      setError(caught instanceof Error ? caught.message : t.failed);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form className="natega-form" onSubmit={handleSubmit}>
        <label htmlFor="natega-query">{t.label}</label>
        <div className="natega-input-wrap">
          <Search aria-hidden="true" size={22} />
          <input
            id="natega-query"
            inputMode="search"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.placeholder}
          />
          <button type="submit" disabled={loading}>
            {loading ? <LoaderCircle className="natega-spinner" aria-hidden="true" size={20} /> : null}
            {loading ? t.searching : t.search}
          </button>
        </div>
        <p className="natega-hint">{t.hint}</p>
      </form>

      {error ? (
        <div className="natega-message natega-error" role="alert">
          <AlertCircle aria-hidden="true" size={20} />
          {error}
        </div>
      ) : null}

      {searched && results.length === 0 ? (
        <div className="natega-message" role="status">
          {t.noResults}
        </div>
      ) : null}

      {results.length > 0 ? (
        <section className="natega-results" aria-live="polite" aria-label="نتائج البحث">
          <div className="natega-results-heading">
            <h2>{t.result}</h2>
            <span>{results.length === MAX_RESULTS ? `${t.first} ${MAX_RESULTS} ${t.results}` : `${results.length} ${t.results}`}</span>
          </div>
          <div className="natega-result-grid">
            {results.map(([seat, name, total, status]) => (
              <article className="natega-result-card" key={seat}>
                <div className="natega-student">
                  <UserRound aria-hidden="true" size={22} />
                  <div>
                    <span>{t.student}</span>
                    <h3>{name}</h3>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt><Hash aria-hidden="true" size={16} /> {t.seat}</dt>
                    <dd>{seat}</dd>
                  </div>
                  <div>
                    <dt>{t.total}</dt>
                    <dd>{total} / {MAX_TOTAL}</dd>
                  </div>
                  <div>
                    <dt>{t.percentage}</dt>
                    <dd>{((Number(total) / MAX_TOTAL) * 100).toFixed(2)}%</dd>
                  </div>
                  <div>
                    <dt>{t.rankWithRepetition}</dt>
                    <dd>{manifest.scoreStats[total]?.rankWithRepetition.toLocaleString(locale === "ar" ? "ar-EG" : "en-US") ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>{t.rankWithoutRepetition}</dt>
                    <dd>{manifest.scoreStats[total]?.rankWithoutRepetition.toLocaleString(locale === "ar" ? "ar-EG" : "en-US") ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>{t.sameScoreCount}</dt>
                    <dd>{manifest.scoreStats[total]?.sameScoreCount.toLocaleString(locale === "ar" ? "ar-EG" : "en-US") ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>{t.status}</dt>
                    <dd>{status}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <p className="natega-dataset-note">
        {t.dataset} {new Intl.NumberFormat(locale === "ar" ? "ar-EG" : "en-US").format(manifest.count)} {t.students}
      </p>
    </>
  );
}
