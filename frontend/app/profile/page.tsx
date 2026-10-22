"use client";

import { useCallback, useEffect, useState } from "react";

import { BackupList } from "@/components/BackupList";
import { ProfileForm } from "@/components/ProfileForm";
import { YamlEditor } from "@/components/YamlEditor";
import { api, type Backup, type ProfileResponse } from "@/lib/api";

export default function ProfilePage() {
  const [data, setData] = useState<ProfileResponse | null>(null);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

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
  const heading = "text-lg font-semibold";

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Profile</h1>
      {loadError && <p role="alert" className="text-sm text-red-600">Could not load the profile: {loadError}</p>}
      {data && !data.profile && (
        <ul role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {data.errors.map((e) => (
            <li key={e.loc + e.msg}>{e.loc ? `${e.loc}: ${e.msg}` : e.msg}</li>
          ))}
        </ul>
      )}
      {data?.profile && (
        <>
          <p className="text-sm text-zinc-500">Editing preferences for {data.profile.personal_info.full_name}.</p>
          <h2 className={heading}>Preferences</h2>
          <ProfileForm key={data.yaml} initial={data.profile.preferences} onSave={save} />
        </>
      )}
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
