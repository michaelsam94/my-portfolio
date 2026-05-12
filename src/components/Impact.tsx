import { useEffect, useMemo, useRef, useState } from "react";
import { animate, motion, useInView } from "framer-motion";
import { impact } from "../data/portfolio";
import {
  scrollCardList,
  scrollListViewport,
  scrollEase,
} from "../motion/scrollReveal";
import "./Impact.css";

const scrollStat = {
  hidden: { opacity: 0, y: 22, scale: 0.94 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.48, ease: scrollEase },
  },
};

/** Count-up target + formatter for strings like `10+`, `120k+`, `99.9%`. */
function parseImpactValue(raw: string) {
  const value = raw.trim();
  const match = value.match(/^(\d+(?:\.\d+)?)(.*)$/);
  if (!match) return null;
  const to = Number(match[1]);
  if (Number.isNaN(to)) return null;
  const suffix = match[2] ?? "";
  const dot = match[1].indexOf(".");
  const decimals = dot === -1 ? 0 : match[1].length - dot - 1;

  const format = (n: number) => {
    const clamped = Math.min(Math.max(n, 0), to);
    if (decimals > 0) {
      return `${clamped.toFixed(decimals)}${suffix}`;
    }
    return `${Math.round(clamped)}${suffix}`;
  };

  return { to, format, value };
}

const COUNT_DURATION = 2.35;
const COUNT_STAGGER = 0.12;

function ImpactAnimatedValue({
  raw,
  start,
  delay,
}: {
  raw: string;
  start: boolean;
  delay: number;
}) {
  const parsed = useMemo(() => parseImpactValue(raw), [raw]);
  const [text, setText] = useState(() => (parsed ? parsed.format(0) : raw));

  useEffect(() => {
    if (!start || !parsed) return;

    const { to, format, value } = parsed;
    setText(format(0));

    const controls = animate(0, to, {
      duration: COUNT_DURATION,
      delay,
      ease: scrollEase,
      onUpdate: (latest) => setText(format(latest)),
      onComplete: () => setText(value),
    });

    return () => controls.stop();
  }, [start, delay, parsed]);

  if (!parsed) {
    return <span className="impact-value">{raw}</span>;
  }

  return <span className="impact-value">{text}</span>;
}

export default function Impact() {
  const gridRef = useRef<HTMLDivElement>(null);
  const inView = useInView(gridRef, { once: true, amount: 0.2, margin: "0px 0px -8% 0px" });

  return (
    <section className="section impact">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Impact at a Glance
      </motion.h2>
      <motion.div
        ref={gridRef}
        className="impact-grid"
        variants={scrollCardList}
        initial="hidden"
        whileInView="show"
        viewport={scrollListViewport}
      >
        {impact.map(({ value, label }, index) => (
          <motion.div key={label} className="impact-card glass-card" variants={scrollStat}>
            <ImpactAnimatedValue raw={value} start={inView} delay={index * COUNT_STAGGER} />
            <span className="impact-label">{label}</span>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
