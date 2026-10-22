"use client";

import { useState } from "react";

import { type FieldError, fieldErrors } from "@/lib/api";

/** Raw profile YAML (placeholders intact), saved verbatim after server-side validation. */
export function YamlEditor(props: { initial: string; onSave: (yaml: string) => Promise<void> }) {
  const [text, setText] = useState(props.initial);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [saved, setSaved] = useState(false);

  async function save() {
    try {
      await props.onSave(text);
      setErrors([]);
      setSaved(true);
    } catch (error) {
      setErrors(fieldErrors(error));
      setSaved(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="profile-yaml" className="text-sm font-medium">Profile YAML</label>
      <textarea
        id="profile-yaml"
        spellCheck={false}
        rows={24}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setSaved(false);
        }}
        className="rounded-md border border-zinc-300 bg-white p-3 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
      />
      {errors.length > 0 && (
        <ul role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {errors.map((e) => <li key={e.loc + e.msg}>{e.loc ? `${e.loc}: ${e.msg}` : e.msg}</li>)}
        </ul>
      )}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={text === props.initial}
          className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
        >
          Save YAML
        </button>
        {saved && <p className="text-sm text-zinc-500">Saved. The previous version was backed up.</p>}
      </div>
    </div>
  );
}
