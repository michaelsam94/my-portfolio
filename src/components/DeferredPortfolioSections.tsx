import { lazy, Suspense, useEffect, useState } from "react";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (id: number) => void;
};

const About = lazy(() => import("./About"));
const Experience = lazy(() => import("./Experience"));
const Projects = lazy(() => import("./Projects"));
const Motion = lazy(() => import("./Motion"));
const PlayStore = lazy(() => import("./PlayStore"));
const Impact = lazy(() => import("./Impact"));
const OpenSource = lazy(() => import("./OpenSource"));
const Skills = lazy(() => import("./Skills"));
const Certifications = lazy(() => import("./Certifications"));
const Citations = lazy(() => import("./Citations"));
const Contact = lazy(() => import("./Contact"));

function scheduleAfterPageSettles(callback: () => void) {
  const idleWindow = window as IdleWindow;
  let timeoutId = 0;
  let idleId = 0;
  let didRun = false;

  const cleanup = () => {
    window.removeEventListener("scroll", run, listenerOptions);
    window.removeEventListener("pointerdown", run, listenerOptions);
    window.removeEventListener("keydown", run);
    window.removeEventListener("hashchange", run);
    window.clearTimeout(timeoutId);
  };

  const run = () => {
    if (didRun) {
      return;
    }

    didRun = true;
    cleanup();

    if (idleWindow.requestIdleCallback) {
      idleId = idleWindow.requestIdleCallback(callback, { timeout: 1000 });
      return;
    }

    window.setTimeout(callback, 1);
  };

  const listenerOptions = true;

  window.addEventListener("scroll", run, listenerOptions);
  window.addEventListener("pointerdown", run, listenerOptions);
  window.addEventListener("keydown", run);
  window.addEventListener("hashchange", run);

  timeoutId = window.setTimeout(run, 5000);

  if (window.location.hash) {
    window.setTimeout(run, 1);
  }

  return () => {
    cleanup();
    if (idleId && idleWindow.cancelIdleCallback) {
      idleWindow.cancelIdleCallback(idleId);
    }
  };
}

export default function DeferredPortfolioSections() {
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    return scheduleAfterPageSettles(() => setShouldRender(true));
  }, []);

  useEffect(() => {
    if (!shouldRender || !window.location.hash) {
      return;
    }

    window.requestAnimationFrame(() => {
      const targetId = decodeURIComponent(window.location.hash.slice(1));
      document.getElementById(targetId)?.scrollIntoView();
    });
  }, [shouldRender]);

  if (!shouldRender) {
    return null;
  }

  return (
    <Suspense fallback={null}>
      <About />
      <Experience />
      <Projects />
      <Motion />
      <PlayStore />
      <Impact />
      <OpenSource />
      <Skills />
      <Certifications />
      <Citations />
      <Contact />
    </Suspense>
  );
}
