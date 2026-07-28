"use client";

import { FormEvent, useState } from "react";
import { Search, UserRound, Hash, LoaderCircle, AlertCircle } from "lucide-react";

type ResultRecord = [seat: string, name: string, total: string, status: string];
type Manifest = {
  count: number;
  nameShards: Record<string, string>;
  seatPrefixes: string[];
};

const MAX_RESULTS = 25;

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

export default function NategaSearch({ manifest }: { manifest: Manifest }) {
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
      setError("اكتب الاسم أو رقم الجلوس أولاً.");
      return;
    }

    setLoading(true);
    try {
      const isSeatNumber = /^\d+$/.test(value);
      let matches: ResultRecord[] = [];

      if (isSeatNumber) {
        if (value.length < 3) {
          throw new Error("رقم الجلوس يجب أن يتكون من 3 أرقام على الأقل.");
        }
        const response = await fetch(`/natega-data/seats/${value.slice(0, 3)}.json`);
        if (response.ok) {
          const records = (await response.json()) as ResultRecord[];
          matches = records.filter((record) => record[0] === value);
        }
      } else {
        const normalized = normalizeArabic(value);
        if (normalized.length < 3) {
          throw new Error("اكتب 3 أحرف على الأقل للبحث بالاسم.");
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
      setError(caught instanceof Error ? caught.message : "تعذر البحث الآن. حاول مرة أخرى.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form className="natega-form" onSubmit={handleSubmit}>
        <label htmlFor="natega-query">الاسم أو رقم الجلوس</label>
        <div className="natega-input-wrap">
          <Search aria-hidden="true" size={22} />
          <input
            id="natega-query"
            inputMode="search"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="مثال: أحمد محمد أو 2001970"
          />
          <button type="submit" disabled={loading}>
            {loading ? <LoaderCircle className="natega-spinner" aria-hidden="true" size={20} /> : null}
            {loading ? "جاري البحث" : "عرض النتيجة"}
          </button>
        </div>
        <p className="natega-hint">يمكنك البحث بالاسم الكامل أو جزء منه، أو إدخال رقم الجلوس بدقة.</p>
      </form>

      {error ? (
        <div className="natega-message natega-error" role="alert">
          <AlertCircle aria-hidden="true" size={20} />
          {error}
        </div>
      ) : null}

      {searched && results.length === 0 ? (
        <div className="natega-message" role="status">
          لم نعثر على نتيجة مطابقة. راجع الاسم أو رقم الجلوس وحاول مرة أخرى.
        </div>
      ) : null}

      {results.length > 0 ? (
        <section className="natega-results" aria-live="polite" aria-label="نتائج البحث">
          <div className="natega-results-heading">
            <h2>النتيجة</h2>
            <span>{results.length === MAX_RESULTS ? `أول ${MAX_RESULTS} نتيجة` : `${results.length} نتيجة`}</span>
          </div>
          <div className="natega-result-grid">
            {results.map(([seat, name, total, status]) => (
              <article className="natega-result-card" key={seat}>
                <div className="natega-student">
                  <UserRound aria-hidden="true" size={22} />
                  <div>
                    <span>اسم الطالب</span>
                    <h3>{name}</h3>
                  </div>
                </div>
                <dl>
                  <div>
                    <dt><Hash aria-hidden="true" size={16} /> رقم الجلوس</dt>
                    <dd>{seat}</dd>
                  </div>
                  <div>
                    <dt>المجموع</dt>
                    <dd>{total}</dd>
                  </div>
                  <div>
                    <dt>الحالة</dt>
                    <dd>{status}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <p className="natega-dataset-note">
        قاعدة البيانات الحالية تشمل {new Intl.NumberFormat("ar-EG").format(manifest.count)} طالب وطالبة.
      </p>
    </>
  );
}
