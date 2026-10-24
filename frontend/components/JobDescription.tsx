import { Fragment } from "react";

function renderInline(text: string) {
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

export function normalizeDescription(raw: string): string {
  if (!raw) return "";

  let text = raw.trim();

  // If text already has structure (markdown, list items, or line breaks), keep it intact
  const hasStructure =
    text.includes("\n- ") ||
    text.includes("\n* ") ||
    text.includes("\n• ") ||
    text.includes("\n\n") ||
    (text.match(/\n/g) || []).length >= 2;

  if (hasStructure) {
    return text.replace(/^[•\u2022]\s*/gm, "- ");
  }

  // 1. Separate before major section headings
  const sectionKeywords = [
    "Accountabilities",
    "Responsibilities",
    "Requirements",
    "Qualifications",
    "Required Qualifications",
    "Preferred Qualifications",
    "Minimum Qualifications",
    "Basic Qualifications",
    "Key Responsibilities",
    "What You(?:'|’)?ll Do",
    "What You(?:'|’)?ll Bring",
    "What We Offer",
    "What We(?:'|’)?re Looking For",
    "What You Need",
    "About Us",
    "About the Company",
    "About the Role",
    "About the Team",
    "About [A-Z][a-zA-Z\\s]+ Team",
    "Role Overview",
    "Job Overview",
    "Technical Skills",
    "Nice to Have",
    "Preferred Skills",
    "Perks & Benefits",
    "Benefits",
    "Compensation",
    "Who We Are",
    "The Role",
    "Why Join Us",
    "How You Will Contribute",
    "Our Values",
    "Life at [A-Z][a-zA-Z]+",
    "Equal Opportunity Employer",
    "ABOUT THE [A-Z\\s]+",
    "THE ROLE",
    "WHAT YOU(?:'|’)?LL DO",
    "WHAT YOU(?:'|’)?LL BRING",
    "REQUIRED QUALIFICATIONS",
    "PREFERRED QUALIFICATIONS",
    "MINIMUM QUALIFICATIONS",
    "WHO WE ARE",
    "WHY JOIN US",
    "COMPENSATION AND BENEFITS",
  ];

  const sectionPattern = new RegExp(
    `(?:^|(?<=[.!?\\n])\\s+)((?:${sectionKeywords.join("|")}):?)(?=\\s|$)`,
    "gi",
  );
  text = text.replace(sectionPattern, "\n\n## $1\n\n");

  // 2. Separate category-colon bullet items:
  // e.g. "Full Stack Development: Design..." or "API Integration: Build..."
  text = text.replace(
    /(?:^|(?<=[.!?\n])\s*)([A-Z][A-Za-z0-9& -]{2,35}:)(?!\/\/)\s*/g,
    "\n- **$1** ",
  );

  // 3. Separate bullet items starting with common action verbs / qualification starters after sentence end
  const bulletStarters = [
    "Experience",
    "Proficiency",
    "Proven",
    "Comfortable",
    "Strong",
    "Demonstrated",
    "Working knowledge",
    "Familiarity",
    "Deep understanding",
    "Ability",
    "Track record",
    "Bachelor",
    "Master",
    "Degree",
    "\\d+[\\+\\-]?\\s*years?",
    "Build",
    "Design",
    "Develop",
    "Maintain",
    "Lead",
    "Drive",
    "Create",
    "Implement",
    "Collaborate",
    "Partner",
    "Work",
    "Own",
    "Deliver",
    "Write",
    "Package",
    "Evaluate",
    "Ensure",
    "Manage",
  ];
  const startersPattern = new RegExp(
    `(?<=[.!?])\\s+((?:${bulletStarters.join("|")})\\b(?!:))`,
    "g",
  );
  text = text.replace(startersPattern, "\n- $1");

  // 4. Separate inline bullet characters like • or -
  text = text.replace(/\s+[•\u2022]\s*/g, "\n- ");
  text = text.replace(/\s+-\s+(?=[A-Z])/g, "\n- ");

  // 5. If a heading is immediately followed by body text without a newline, split it
  text = text.replace(/^(## [^\n]+?):?\s+([A-Z])/gm, "$1\n\n$2");

  return text.trim();
}

export function JobDescription({ text }: { text: string }) {
  const normalized = normalizeDescription(text);
  const blocks = normalized
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);

  if (blocks.length === 0) {
    return <p className="text-zinc-500">No description provided for this posting.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, i) => {
        if (block.startsWith("# ")) {
          return (
            <h2 key={i} className="pt-2 text-base font-bold text-zinc-900 dark:text-zinc-100">
              {renderInline(block.slice(2))}
            </h2>
          );
        }
        if (block.startsWith("## ")) {
          return (
            <h3 key={i} className="pt-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {renderInline(block.slice(3))}
            </h3>
          );
        }
        if (block.startsWith("### ")) {
          return (
            <h4
              key={i}
              className="pt-1 text-xs font-semibold uppercase tracking-wider text-zinc-800 dark:text-zinc-200"
            >
              {renderInline(block.slice(4))}
            </h4>
          );
        }

        const lines = block.split("\n");
        // Check if all lines are bullets
        if (lines.every((line) => line.startsWith("- ") || line.startsWith("* ") || line.startsWith("• "))) {
          return (
            <ul key={i} className="flex list-disc flex-col gap-1 pl-5 marker:text-zinc-400">
              {lines.map((line, j) => (
                <li key={j} className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                  {renderInline(line.slice(2))}
                </li>
              ))}
            </ul>
          );
        }

        // Check if block has mixed intro line and bullets
        const hasBullets = lines.some((l) => l.startsWith("- ") || l.startsWith("* ") || l.startsWith("• "));
        if (hasBullets) {
          const elements: React.ReactNode[] = [];
          let currentBullets: string[] = [];

          const flushBullets = () => {
            if (currentBullets.length > 0) {
              const bKey = elements.length;
              elements.push(
                <ul key={bKey} className="flex list-disc flex-col gap-1 pl-5 marker:text-zinc-400">
                  {currentBullets.map((bullet, j) => (
                    <li key={j} className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                      {renderInline(bullet)}
                    </li>
                  ))}
                </ul>,
              );
              currentBullets = [];
            }
          };

          for (let idx = 0; idx < lines.length; idx++) {
            const line = lines[idx];
            if (line.startsWith("- ") || line.startsWith("* ") || line.startsWith("• ")) {
              currentBullets.push(line.slice(2));
            } else {
              flushBullets();
              elements.push(
                <p key={elements.length} className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                  {renderInline(line)}
                </p>,
              );
            }
          }
          flushBullets();
          return <Fragment key={i}>{elements}</Fragment>;
        }

        // Regular paragraph block
        return (
          <p key={i}>
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
  );
}
