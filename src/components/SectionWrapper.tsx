import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type SectionWrapperProps = {
  id: string;
  heading: string;
  headingId: string;
  children: ReactNode;
  className?: string;
};

export default function SectionWrapper({ id, heading, headingId, children, className }: SectionWrapperProps) {
  return (
    <section id={id} aria-labelledby={headingId} className={cn("section", className)}>
      <h2 id={headingId} className="section-label">
        {heading}
      </h2>
      {children}
    </section>
  );
}
