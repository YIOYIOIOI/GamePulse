import { Fragment, type ReactNode } from "react";
import { cleanReview, issueBlocks, issueExcerpt } from "../format";
import type { Evidence } from "../types";

const escape = (term: string) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// The English keyword rules match whole words ("UI" but not "build"), like the server's \b rules;
// the Chinese and Russian rules match stems, so those terms are found anywhere in a word.
const termPattern = (term: string) =>
  /^[\x20-\x7e]+$/.test(term)
    ? `(?<![A-Za-z0-9])${escape(term)}(?![A-Za-z0-9])`
    : escape(term);

/** Wraps every occurrence of the matched keywords in <mark>. */
export function Highlighted({
  text,
  terms,
}: {
  text: string;
  terms: string[];
}) {
  const unique = [...new Set(terms.map((t) => t.trim()).filter(Boolean))];
  if (!unique.length) return <>{text}</>;
  const pattern = new RegExp(`(${unique.map(termPattern).join("|")})`, "gi");
  const lower = new Set(unique.map((t) => t.toLowerCase()));
  return (
    <>
      {text
        .split(pattern)
        .map((part, i) =>
          i % 2 === 1 && lower.has(part.toLowerCase()) ? (
            <mark key={i}>{part}</mark>
          ) : (
            <Fragment key={i}>{part}</Fragment>
          ),
        )}
    </>
  );
}

/** A short preview of a review or an issue, as shown in lists. */
export function excerpt(e: Evidence, length = 220) {
  const body =
    e.source === "steam" ? cleanReview(e.text) : issueExcerpt(e.text);
  const flat = body
    .replace(/https?:\/\/\S+/g, "[链接]")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > length ? flat.slice(0, length).trimEnd() + "…" : flat;
}

/** The full text: reviews as written, issues with their form headings as section titles. */
export function FullText({
  evidence,
  terms = [],
}: {
  evidence: Evidence;
  terms?: string[];
}) {
  if (evidence.source === "steam")
    return (
      <div className="full-text">
        <Highlighted
          text={cleanReview(evidence.text) || "（评论没有正文）"}
          terms={terms}
        />
      </div>
    );
  const blocks = issueBlocks(evidence.text);
  if (!blocks.length)
    return <div className="full-text muted">（issue 没有正文）</div>;
  return (
    <div className="full-text issue">
      {blocks.map((block, i): ReactNode => {
        if (block.kind === "heading") return <h4 key={i}>{block.text}</h4>;
        if (block.kind === "code") return <pre key={i}>{block.text}</pre>;
        return (
          <p key={i}>
            <Highlighted text={block.text} terms={terms} />
          </p>
        );
      })}
    </div>
  );
}
