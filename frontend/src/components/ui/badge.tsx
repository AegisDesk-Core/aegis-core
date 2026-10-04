import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "teal" | "accent" | "danger" | "secondary" | "outline";
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  const base =
    "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium transition-colors select-none";

  const variants = {
    default: "bg-[#22262c] text-[#989b9f] border border-[#2e3339]",
    teal: "bg-[#5fa8a0]/15 text-[#5fa8a0] border border-[#5fa8a0]/30",
    accent: "bg-[#c68a3d]/20 text-[#e5b77c] border border-[#c68a3d]/40",
    danger: "bg-[#c05a4f]/20 text-[#e67568] border border-[#c05a4f]/35",
    secondary: "bg-[#1b1f24] text-[#6c7074] border border-[#26292f]",
    outline: "border border-[#2e3339] text-[#989b9f]",
  };

  return (
    <div className={cn(base, variants[variant], className)} {...props} />
  );
}
