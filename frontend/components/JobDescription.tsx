import { Fragment } from "react";

// Renders the Markdown subset produced at ingestion (src/ingestion/base.py html_to_markdown):
// `## ` headings, `- ` bullets, and paragraphs separated by blank lines. No raw HTML is
// ever injected, so descriptions from third-party boards can't run script.
export function JobDescription({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  if (blocks.length === 0) {
    return <p className="text-zinc-500">No description provided for this posting.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, i) => {
        if (block.startsWith("## ")) {
          return (
            <h3 key={i} className="pt-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {block.slice(3)}
            </h3>
          );
        }
        const lines = block.split("\n");
        if (lines.every((line) => line.startsWith("- "))) {
          return (
            <ul key={i} className="flex list-disc flex-col gap-1 pl-5 marker:text-zinc-400">
              {lines.map((line, j) => (
                <li key={j}>{line.slice(2)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            {lines.map((line, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {line}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
