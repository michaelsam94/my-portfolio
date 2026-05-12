/** Shared easing — matches hero motion for a cohesive feel */
export const scrollEase = [0.22, 1, 0.36, 1] as const;

/** Parent list: light fade + stagger children as the block scrolls into view */
export const scrollCardList = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      duration: 0.35,
      ease: scrollEase,
      staggerChildren: 0.08,
      delayChildren: 0.04,
    },
  },
};

/** Tighter stagger for denser grids */
export const scrollCardListDense = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      duration: 0.3,
      ease: scrollEase,
      staggerChildren: 0.055,
      delayChildren: 0.03,
    },
  },
};

/** Standard card: fade, lift, slight scale */
export const scrollCard = {
  hidden: { opacity: 0, y: 28, scale: 0.97 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.5, ease: scrollEase },
  },
};

/** Lighter motion for smaller tiles */
export const scrollCardCompact = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.42, ease: scrollEase },
  },
};

export const scrollListViewport = {
  once: true,
  margin: "0px 0px -10% 0px",
  amount: 0.15,
} as const;
