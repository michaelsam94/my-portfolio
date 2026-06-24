"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, Mail } from "lucide-react";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import { springPop } from "@/lib/motion";

export default function CopyEmail({ email }: { email: string }) {
  const { copied, error, copy } = useCopyToClipboard(email);

  return (
    <>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Email copied to clipboard" : "Copy email address"}
        className="copy-email"
      >
        <AnimatePresence mode="wait" initial={false}>
          {copied ? (
            <motion.span
              key="check"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={springPop}
            >
              <Check size={16} aria-hidden="true" />
            </motion.span>
          ) : (
            <motion.span
              key="mail"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={springPop}
            >
              <Mail size={16} aria-hidden="true" />
            </motion.span>
          )}
        </AnimatePresence>
        {copied ? "Copied" : email}
      </button>
      <div role="status" aria-live="polite" className="sr-only">
        {copied ? "Email copied to clipboard" : error}
      </div>
    </>
  );
}
