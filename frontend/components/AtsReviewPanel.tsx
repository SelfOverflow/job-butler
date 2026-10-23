import type { AtsReview, RequirementCheck } from "@/lib/api";

const VERDICT: Record<AtsReview["verdict"], { label: string; className: string }> = {
  shortlist: { label: "Shortlist", className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" },
  borderline: { label: "Borderline", className: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300" },
  reject: { label: "Reject", className: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300" },
};

const STATUS: Record<RequirementCheck["status"], { label: string; className: string }> = {
  covered: { label: "Covered", className: "text-emerald-700 dark:text-emerald-400" },
  synonym_only: { label: "Synonym only", className: "text-amber-700 dark:text-amber-400" },
  missing_have_it: { label: "Missing (you have it)", className: "text-amber-700 dark:text-amber-400" },
  gap: { label: "Gap", className: "text-red-700 dark:text-red-400" },
};

const pill = "rounded-full px-2.5 py-0.5 text-xs font-medium";

export function AtsReviewPanel({ review }: { review: AtsReview }) {
  const verdict = VERDICT[review.verdict];
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">Recruiter ATS review</h2>
        <div className="flex items-center gap-2">
          <span aria-label={`ATS score ${review.score} of 100`} className={`${pill} bg-zinc-100 dark:bg-zinc-800`}>
            {review.score}
          </span>
          <span className={`${pill} ${verdict.className}`}>{verdict.label}</span>
        </div>
      </div>

      {review.ungrounded_claims.length > 0 && (
        <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/60 dark:text-red-300">
          Claims the reviewer could not trace to your profile: {review.ungrounded_claims.join("; ")}
        </div>
      )}

      {review.requirements.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-zinc-500">
            <tr>
              <th className="py-1 font-medium">Requirement</th>
              <th className="py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {review.requirements.map((r) => (
              <tr key={r.requirement} className="border-t border-zinc-100 dark:border-zinc-800" title={r.note}>
                <td className="py-1.5">
                  {r.requirement}
                  {r.priority === "preferred" && <span className="ml-1 text-xs text-zinc-500">(preferred)</span>}
                </td>
                <td className={`py-1.5 ${STATUS[r.status].className}`}>{STATUS[r.status].label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {review.issues.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-zinc-700 dark:text-zinc-300">
          {review.issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
