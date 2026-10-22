"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Download, ShieldCheck } from "lucide-react";

import { BackupList } from "@/components/BackupList";
import { ProfileForm } from "@/components/ProfileForm";
import { YamlEditor } from "@/components/YamlEditor";
import { api, type Backup, type ProfileResponse } from "@/lib/api";

export default function ProfilePage() {
  const [data, setData] = useState<ProfileResponse | null>(null);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Validation state
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<{
    valid: boolean;
    full_name: string;
    bullet_count: number;
    role_count: number;
    star_story_count: number;
    screening_count: number;
  } | null>(null);

  // Screening query tester
  const [queryText, setQueryText] = useState("");
  const [queryResult, setQueryResult] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [querying, setQuerying] = useState(false);

  // Add bullet
  const [bulletRole, setBulletRole] = useState("");
  const [bulletText, setBulletText] = useState("");
  const [bulletSkills, setBulletSkills] = useState("");
  const [bulletResult, setBulletResult] = useState<string | null>(null);
  const [addingBullet, setAddingBullet] = useState(false);

  const load = useCallback(
    () =>
      Promise.all([api.profile(), api.backups()]).then(
        ([profile, list]) => {
          setData(profile);
          setBackups(list);
        },
        (e: Error) => setLoadError(e.message),
      ),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  const save = async (set: Record<string, string>) => {
    await api.updateProfile({ set });
    await load();
  };
  const saveYaml = async (yaml: string) => {
    await api.updateProfile({ yaml });
    await load();
  };
  const restore = async (name: string) => {
    await api.restoreBackup(name);
    await load();
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const res = await api.validateProfile();
      setValidation(res);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setValidating(false);
    }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryText.trim()) return;
    setQuerying(true);
    setQueryError(null);
    setQueryResult(null);
    try {
      const res = await api.queryScreening(queryText.trim());
      setQueryResult(String(res.answer));
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : String(err));
    } finally {
      setQuerying(false);
    }
  };

  const handleAddBullet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulletRole.trim() || !bulletText.trim()) return;
    setAddingBullet(true);
    setBulletResult(null);
    try {
      const skills = bulletSkills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await api.addBullet(bulletRole.trim(), bulletText.trim(), skills);
      setBulletResult(`Added bullet ${res.bullet_id}`);
      setBulletText("");
      setBulletSkills("");
      await load();
    } catch (err) {
      setBulletResult(`Failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setAddingBullet(false);
    }
  };

  const heading = "text-lg font-semibold";
  const btnSecondary =
    "inline-flex items-center gap-1.5 rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800";
  const inputClass =
    "rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Profile</h1>
          {data?.profile && (
            <p className="text-sm text-zinc-500">
              Editing preferences for {data.profile.personal_info.full_name}.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={validating}
            onClick={handleValidate}
            className={btnSecondary}
          >
            <ShieldCheck size={14} aria-hidden />
            {validating ? "Validating…" : "Validate Profile"}
          </button>
          <a
            href="/api/profile/export-master"
            download="master_resume.md"
            className={btnSecondary}
          >
            <Download size={14} aria-hidden />
            Export Master
          </a>
        </div>
      </div>

      {validation && (
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
          <CheckCircle2 size={16} aria-hidden />
          <span>
            Valid: {validation.role_count} roles, {validation.bullet_count} bullets,{" "}
            {validation.screening_count} screening answers.
          </span>
        </div>
      )}

      {loadError && (
        <p role="alert" className="text-sm text-red-600">
          Could not load the profile: {loadError}
        </p>
      )}

      {data && !data.profile && (
        <ul
          role="alert"
          className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {data.errors.map((e) => (
            <li key={e.loc + e.msg}>{e.loc ? `${e.loc}: ${e.msg}` : e.msg}</li>
          ))}
        </ul>
      )}

      {data?.profile && (
        <>
          <h2 className={heading}>Preferences</h2>
          <ProfileForm key={data.yaml} initial={data.profile.preferences} onSave={save} />
        </>
      )}

      {/* Screening Questions Query Tester */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className={heading}>Test Screening Answers</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Query candidate answers to screening questions using keyword and semantic matching.
        </p>
        <form onSubmit={handleQuery} className="mt-3 flex gap-2">
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="Ask a screening question (e.g. legally authorized?)..."
            className={`flex-1 ${inputClass}`}
          />
          <button
            type="submit"
            disabled={querying}
            className="rounded-md bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            {querying ? "Checking…" : "Test Answer"}
          </button>
        </form>
        {queryResult !== null && (
          <p className="mt-3 text-xs text-emerald-700 dark:text-emerald-400">
            Answer: {queryResult}
          </p>
        )}
        {queryError && (
          <p role="alert" className="mt-3 text-xs text-red-600 dark:text-red-400">
            {queryError}
          </p>
        )}
      </div>

      {/* Add Experience Bullet */}
      <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className={heading}>Add Experience Bullet</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Append an achievement bullet with associated skills to a specific work experience role.
        </p>
        <form onSubmit={handleAddBullet} className="mt-3 flex flex-col gap-3">
          <input
            type="text"
            value={bulletRole}
            onChange={(e) => setBulletRole(e.target.value)}
            placeholder="Role ID (e.g. exp_company_alpha)"
            className={inputClass}
          />
          <textarea
            value={bulletText}
            onChange={(e) => setBulletText(e.target.value)}
            placeholder="Bullet text (action-driven achievement)"
            rows={2}
            className={inputClass}
          />
          <input
            type="text"
            value={bulletSkills}
            onChange={(e) => setBulletSkills(e.target.value)}
            placeholder="Skills (comma-separated, e.g. Python, Docker)"
            className={inputClass}
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={addingBullet}
              className="rounded-md bg-zinc-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {addingBullet ? "Adding…" : "Add Bullet"}
            </button>
            {bulletResult && (
              <span className="text-xs text-zinc-600 dark:text-zinc-400">{bulletResult}</span>
            )}
          </div>
        </form>
      </div>

      {data && (
        <>
          <h2 className={heading}>Raw YAML</h2>
          <YamlEditor key={data.yaml} initial={data.yaml} onSave={saveYaml} />
          <h2 className={heading}>Backups</h2>
          <BackupList backups={backups} onRestore={restore} />
        </>
      )}
    </section>
  );
}
