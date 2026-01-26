import type { ReactNode } from "react";

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function extractTerms(query: string): string[] {
  const terms: string[] = [];
  const regex = /"([^"]+)"|(\S+)/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(query)) !== null) {
    const raw = match[1] ?? match[2] ?? "";
    if (!raw) continue;
    const upper = raw.toUpperCase();
    if (upper === "OR" || upper === "AND") continue;
    const cleaned = raw.startsWith("-") ? raw.slice(1) : raw;
    const value = cleaned.endsWith("*") ? cleaned.slice(0, -1) : cleaned;
    const trimmed = value.trim();
    if (trimmed) {
      terms.push(trimmed);
    }
  }
  const unique = Array.from(new Set(terms.map((term) => term.toLowerCase())));
  return unique;
}

export function highlightText(text: string, terms: string[]): ReactNode {
  if (!text || terms.length === 0) return text;
  const sorted = [...terms].sort((a, b) => b.length - a.length);
  const pattern = sorted.map(escapeRegex).join("|");
  if (!pattern) return text;
  const splitRegex = new RegExp(`(${pattern})`, "ig");
  const matchRegex = new RegExp(`^(${pattern})$`, "i");
  const parts = text.split(splitRegex);
  return parts.map((part, index) => {
    if (matchRegex.test(part)) {
      return (
        <mark
          key={`${part}-${index}`}
          style={{ backgroundColor: "#ffe7a3", padding: "0 2px" }}
        >
          {part}
        </mark>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}
