import Link from "next/link";

export default function Dashboard() {
  return (
    <section className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="text-sm text-zinc-500">
        Live feed and metrics are coming next. Browse discovered roles on the{" "}
        <Link href="/jobs/" className="underline">
          Jobs
        </Link>{" "}
        page.
      </p>
    </section>
  );
}
