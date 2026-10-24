"use client";

import { Fragment, useState } from "react";
import { Check, Copy, Eye, FileText } from "lucide-react";

function renderInline(text: string) {
  // Parse bold **text** and links or plain text
  const parts = text.split(/(\*\*.*?\*\*|https?:\/\/[^\s]+)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-zinc-900 dark:text-zinc-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("http://") || part.startsWith("https://")) {
      return (
        <a
          key={i}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
        >
          {part}
        </a>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function MarkdownPreview({ markdown }: { markdown: string }) {
  const [view, setView] = useState<"rendered" | "raw">("rendered");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignore clipboard write failure if permissions deny
    }
  };

  const blocks = markdown.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);

  return (
    <div className="w-full rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 pb-3 dark:border-zinc-800">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Master Resume Preview (Markdown)
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500">
            Live preview of your ATS-friendly master resume export.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-900">
            <button
              type="button"
              onClick={() => setView("rendered")}
              className={`inline-flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium transition ${
                view === "rendered"
                  ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              }`}
            >
              <Eye size={13} aria-hidden /> Rendered
            </button>
            <button
              type="button"
              onClick={() => setView("raw")}
              className={`inline-flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium transition ${
                view === "raw"
                  ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              }`}
            >
              <FileText size={13} aria-hidden /> Raw
            </button>
          </div>
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
            title="Copy Markdown"
          >
            {copied ? <Check size={13} className="text-emerald-600" aria-hidden /> : <Copy size={13} aria-hidden />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <div className="mt-4">
        {view === "raw" ? (
          <pre className="max-h-[600px] overflow-auto rounded-lg bg-zinc-50 p-4 font-mono text-xs leading-relaxed text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
            {markdown}
          </pre>
        ) : (
          <div className="flex max-h-[600px] flex-col gap-3 overflow-auto pr-2 text-sm">
            {blocks.map((block, i) => {
              if (block.startsWith("# ")) {
                return (
                  <h1 key={i} className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                    {block.slice(2)}
                  </h1>
                );
              }
              if (block.startsWith("## ")) {
                return (
                  <h2
                    key={i}
                    className="border-b border-zinc-200 pt-2 pb-1 text-base font-semibold text-zinc-900 dark:border-zinc-800 dark:text-zinc-100"
                  >
                    {block.slice(3)}
                  </h2>
                );
              }
              if (block.startsWith("### ")) {
                const lines = block.split("\n");
                return (
                  <div key={i} className="pt-2">
                    <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                      {lines[0].slice(4)}
                    </h3>
                    {lines.slice(1).map((subline, j) => (
                      <p key={j} className="text-xs text-zinc-500 dark:text-zinc-400">
                        {renderInline(subline)}
                      </p>
                    ))}
                  </div>
                );
              }
              const lines = block.split("\n");
              if (lines.every((line) => line.startsWith("- "))) {
                return (
                  <ul key={i} className="list-disc space-y-1 pl-5 text-zinc-700 dark:text-zinc-300 marker:text-zinc-400">
                    {lines.map((line, j) => (
                      <li key={j} className="text-xs leading-relaxed">
                        {renderInline(line.slice(2))}
                      </li>
                    ))}
                  </ul>
                );
              }
              return (
                <p key={i} className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                  {lines.map((line, j) => (
                    <Fragment key={j}>
                      {j > 0 && <br />}
                      {renderInline(line)}
                    </Fragment>
                  ))}
                </p>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
