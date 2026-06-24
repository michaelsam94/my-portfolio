import { cn } from "@/lib/utils";

type StatusTagProps = {
  status: string;
  available: boolean;
};

export default function StatusTag({ status, available }: StatusTagProps) {
  return (
    <span role="status" aria-label={`Status: ${status}`} className="status-tag">
      <span aria-hidden="true" className={cn("status-dot", available ? "available" : "busy")} />
      {status}
    </span>
  );
}
