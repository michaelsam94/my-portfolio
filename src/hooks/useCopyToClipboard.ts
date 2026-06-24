"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useCopyToClipboard(text: string, resetMs = 2000) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const timeoutRef = useRef<number | null>(null);

  const copy = useCallback(async () => {
    setError("");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => setCopied(false), resetMs);
    } catch {
      setError(`Copy blocked. Email: ${text}`);
      setCopied(false);
    }
  }, [resetMs, text]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return { copied, error, copy };
}
