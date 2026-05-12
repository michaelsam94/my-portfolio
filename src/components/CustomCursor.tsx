import { useEffect, useRef, useState } from "react";
import "./CustomCursor.css";

const SELECTOR_INTERACTIVE =
  'a, button, [role="button"], input, textarea, select, label, .btn, .nav-toggle, .projects-card, .play-store-card, .experience-card, .skills-group, .contact-link';

function useFinePointer(): boolean {
  const [ok, setOk] = useState(false);

  useEffect(() => {
    const mqHover = window.matchMedia("(hover: hover)");
    const mqFine = window.matchMedia("(pointer: fine)");
    const mqReduce = window.matchMedia("(prefers-reduced-motion: reduce)");

    const update = () => {
      setOk(mqHover.matches && mqFine.matches && !mqReduce.matches);
    };

    update();
    mqHover.addEventListener("change", update);
    mqFine.addEventListener("change", update);
    mqReduce.addEventListener("change", update);
    return () => {
      mqHover.removeEventListener("change", update);
      mqFine.removeEventListener("change", update);
      mqReduce.removeEventListener("change", update);
    };
  }, []);

  return ok;
}

export default function CustomCursor() {
  const enabled = useFinePointer();
  const rootRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const dotRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef({ x: 0, y: 0 });
  const ringPosRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number>(0);
  const [hover, setHover] = useState(false);
  const [pressing, setPressing] = useState(false);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    if (!enabled) {
      document.body.classList.remove("custom-cursor-on");
      return;
    }

    document.body.classList.add("custom-cursor-on");

    const ringEl = ringRef.current;
    const dotEl = dotRef.current;
    if (!ringEl || !dotEl) {
      return () => {
        document.body.classList.remove("custom-cursor-on");
      };
    }

    const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

    const tick = () => {
      const t = targetRef.current;
      const r = ringPosRef.current;
      r.x = lerp(r.x, t.x, 0.22);
      r.y = lerp(r.y, t.y, 0.2);
      ringEl.style.transform = `translate3d(${r.x}px, ${r.y}px, 0)`;
      dotEl.style.transform = `translate3d(${t.x}px, ${t.y}px, 0)`;
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    const onMove = (e: MouseEvent) => {
      const { clientX: x, clientY: y } = e;
      if (x <= 1 || y <= 1 || x >= window.innerWidth - 1 || y >= window.innerHeight - 1) {
        setHidden(true);
      } else {
        setHidden(false);
      }
      targetRef.current = { x, y };

      const under = document.elementFromPoint(x, y);
      const interactive = under?.closest(SELECTOR_INTERACTIVE);
      setHover(Boolean(interactive));
    };

    const onDown = () => setPressing(true);
    const onUp = () => setPressing(false);

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      document.body.classList.remove("custom-cursor-on");
    };
  }, [enabled]);

  if (!enabled) {
    return null;
  }

  return (
    <div
      ref={rootRef}
      className={`custom-cursor-root${hidden ? " is-hidden" : ""}${hover ? " is-hover" : ""}${pressing ? " is-pressing" : ""}`}
      aria-hidden
    >
      <div ref={ringRef} className="custom-cursor-ring" />
      <div ref={dotRef} className="custom-cursor-dot" />
    </div>
  );
}
