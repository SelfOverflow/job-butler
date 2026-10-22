"use client";

import { type FormEvent, useState } from "react";

import { type FieldError, fieldErrors, type Preferences } from "@/lib/api";

export type ProfileFields = Preferences;
type Key = keyof ProfileFields;
type Kind = "lines" | "number" | "text";

const FIELDS: { key: Key; label: string; kind: Kind; hint?: string }[] = [
  { key: "target_roles", label: "Target roles", kind: "lines", hint: "One per line" },
  { key: "min_base_salary", label: "Minimum base salary", kind: "number", hint: "Annual; needs a currency" },
  { key: "currency", label: "Currency", kind: "text", hint: "ISO code, e.g. INR, EUR, USD" },
  { key: "years_of_experience", label: "Years of experience", kind: "number", hint: "Blank = computed from roles" },
  { key: "excluded_employers", label: "Excluded employers", kind: "lines", hint: "One per line, include aliases" },
];

function toInput(value: ProfileFields[Key]): string {
  if (Array.isArray(value)) return value.join("\n");
  return value === null ? "" : String(value);
}

/** Encode an input as a YAML value for PUT /api/profile `set` (JSON is valid YAML). */
function toYaml(kind: Kind, input: string): string {
  const text = input.trim();
  if (kind === "lines") return JSON.stringify(text.split("\n").map((l) => l.trim()).filter(Boolean));
  if (!text) return "null";
  return kind === "number" ? text : JSON.stringify(text);
}

const box = "rounded-md border bg-white px-3 py-1.5 text-sm dark:bg-zinc-900";

export function ProfileForm(props: {
  initial: ProfileFields;
  onSave: (set: Record<string, string>) => Promise<void>;
}) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, toInput(props.initial[f.key])])) as Record<Key, string>,
  );
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const changes: Record<string, string> = {};
    for (const { key, kind } of FIELDS) {
      const next = toYaml(kind, values[key]);
      if (next !== toYaml(kind, toInput(props.initial[key]))) changes[`preferences.${key}`] = next;
    }
    if (Object.keys(changes).length === 0) return setStatus("No changes to save.");
    try {
      await props.onSave(changes);
      setErrors([]);
      setStatus("Saved. The previous version was backed up.");
    } catch (error) {
      setErrors(fieldErrors(error));
      setStatus(null);
    }
  }

  const errorFor = (key: Key) => errors.find((e) => e.loc === `preferences.${key}`)?.msg;
  const general = errors.filter((e) => !FIELDS.some((f) => e.loc === `preferences.${f.key}`));
  return (
    <form onSubmit={submit} className="flex max-w-xl flex-col gap-4">
      {FIELDS.map(({ key, label, kind, hint }) => {
        const error = errorFor(key);
        const common = {
          id: key,
          value: values[key],
          "aria-invalid": error ? true : undefined,
          "aria-describedby": `${key}-hint`,
          className: `${box} ${error ? "border-red-500" : "border-zinc-300 dark:border-zinc-700"}`,
          onChange: (e: { target: { value: string } }) => setValues((v) => ({ ...v, [key]: e.target.value })),
        };
        return (
          <div key={key} className="flex flex-col gap-1">
            <label htmlFor={key} className="text-sm font-medium">{label}</label>
            {kind === "lines" ? <textarea rows={4} {...common} /> : <input inputMode={kind === "number" ? "decimal" : undefined} {...common} />}
            <p id={`${key}-hint`} className={`text-xs ${error ? "text-red-600" : "text-zinc-500"}`}>{error ?? hint}</p>
          </div>
        );
      })}
      {general.length > 0 && (
        <ul role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {general.map((e) => <li key={e.loc + e.msg}>{e.loc ? `${e.loc}: ${e.msg}` : e.msg}</li>)}
        </ul>
      )}
      <div className="flex items-center gap-3">
        <button type="submit" className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900">
          Save
        </button>
        {status && <p className="text-sm text-zinc-500">{status}</p>}
      </div>
    </form>
  );
}
