export default function HitlPage() {
  return (
    <section className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">Interventions</h1>
      <p className="text-sm text-zinc-500">
        No interventions pending. Once auto-apply is enabled, applications blocked by an account
        sign-up, CAPTCHA, or two-factor prompt will appear here with a screenshot, copy-ready
        answers, and a &ldquo;Mark as applied&rdquo; button.
      </p>
    </section>
  );
}
