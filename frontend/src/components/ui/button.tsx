import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "default" | "sm" | "lg" | "icon";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center rounded-md font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#c68a3d] disabled:pointer-events-none disabled:opacity-40 select-none cursor-pointer";

    const variants = {
      default:
        "bg-[#22262c] text-[#e9e6e0] border border-[#2e3339] hover:bg-[#2a2f37] hover:border-[#3b414a] active:scale-[0.98]",
      primary:
        "bg-[#c68a3d] text-[#1b1300] font-semibold hover:bg-[#d89a4c] shadow-sm active:scale-[0.98]",
      secondary:
        "bg-[#1b1f24] text-[#989b9f] hover:text-[#e9e6e0] hover:bg-[#22262c] border border-[#26292f]",
      outline:
        "border border-[#2e3339] bg-transparent text-[#e9e6e0] hover:bg-[#22262c] hover:border-[#3a4048]",
      ghost:
        "text-[#989b9f] hover:text-[#e9e6e0] hover:bg-[#22262c] border border-transparent",
      danger:
        "bg-[#c05a4f]/20 text-[#e67568] border border-[#c05a4f]/40 hover:bg-[#c05a4f]/30",
    };

    const sizes = {
      default: "h-9 px-3.5 py-1.5 text-sm",
      sm: "h-7 px-2.5 text-xs rounded",
      lg: "h-11 px-5 text-base rounded-lg",
      icon: "h-8 w-8 p-1.5 rounded-md",
    };

    return (
      <button
        ref={ref}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
