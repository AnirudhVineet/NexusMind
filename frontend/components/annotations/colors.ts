import type { AnnotationColor } from "@/types/api";

export const ANNOTATION_COLORS: AnnotationColor[] = [
  "yellow",
  "green",
  "blue",
  "pink",
  "purple",
];

/** Background tint applied to <mark> highlights inside the document viewer. */
export const markClass: Record<AnnotationColor, string> = {
  yellow: "bg-yellow-400/30",
  green: "bg-emerald-400/30",
  blue: "bg-blue-400/30",
  pink: "bg-pink-400/30",
  purple: "bg-purple-400/30",
};

/** Solid swatch used in color pickers and card stripes. */
export const swatchClass: Record<AnnotationColor, string> = {
  yellow: "bg-yellow-400",
  green: "bg-emerald-400",
  blue: "bg-blue-400",
  pink: "bg-pink-400",
  purple: "bg-purple-400",
};
