import React from "react";

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface Props {
  text: string;
  terms: string[];
}

/**
 * Renders `text` with every occurrence of any term in `terms` wrapped in a
 * highlighted <mark>. Matching is case-insensitive.
 */
export function HighlightedText({ text, terms }: Props) {
  const nonEmpty = terms.filter(Boolean);
  if (!nonEmpty.length) return <>{text}</>;

  const pattern = new RegExp(
    `(${nonEmpty.map(escapeRegex).join("|")})`,
    "gi"
  );
  const parts = text.split(pattern);

  const lowerTerms = nonEmpty.map((t) => t.toLowerCase());

  return (
    <>
      {parts.map((part, i) =>
        lowerTerms.includes(part.toLowerCase()) ? (
          <mark
            key={i}
            className="bg-accent/25 text-white not-italic rounded-sm px-0.5"
          >
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        )
      )}
    </>
  );
}
