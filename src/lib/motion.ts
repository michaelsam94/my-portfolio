/**
 * Framer Motion entry for this app. Import from here so `LazyMotion` + `domAnimation`
 * in `main.tsx` can use the smaller DOM animation bundle (better mobile Lighthouse / TBT).
 */
import {
  LazyMotion,
  domAnimation,
  m,
  animate,
  useInView,
  useScroll,
  useTransform,
} from "framer-motion";

export {
  LazyMotion,
  domAnimation,
  m,
  animate,
  useInView,
  useScroll,
  useTransform,
};

/** Alias to `m` — required for `<LazyMotion features={domAnimation} strict>`. */
export const motion = m;
