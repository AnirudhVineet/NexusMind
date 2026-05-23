"use client";

import { forwardRef } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantClass: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent/90",
  secondary: "bg-surface text-white border border-border hover:bg-border",
  ghost: "bg-transparent text-white hover:bg-surface",
  danger: "bg-red-600 text-white hover:bg-red-500",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
        "disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
        variantClass[variant],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
