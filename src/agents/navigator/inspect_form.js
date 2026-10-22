// Collects visible form controls (file inputs may be visually hidden) from the form
// with the most controls. Radios are grouped by name and labelled by their legend.
// Evaluated by form_inspector.inspect_form via page.evaluate().
() => {
  const forms = [...document.querySelectorAll("form")];
  const form = forms.sort((a, b) => b.elements.length - a.elements.length)[0] || document.body;
  const clean = (s) => (s || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
  const visible = (el) => el.type === "file" || !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const labelOf = (el) => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText; }
    const wrap = el.closest("label"); if (wrap) return wrap.innerText;
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    const by = el.getAttribute("aria-labelledby");
    if (by) return by.split(" ").map((id) => document.getElementById(id)?.innerText || "").join(" ");
    return el.placeholder || el.name;
  };
  const selectorOf = (el) => el.id ? `#${CSS.escape(el.id)}` : `[name="${el.name.replace(/"/g, '\\"')}"]`;
  const required = (el, label) => el.required || el.getAttribute("aria-required") === "true" || /\*/.test(label);
  const fields = []; const radios = new Set();
  for (const el of form.querySelectorAll("input, textarea, select")) {
    const type = (el.type || "").toLowerCase();
    if (["hidden", "submit", "button", "reset", "image"].includes(type) || !visible(el) || el.disabled) continue;
    if (type === "radio") {
      if (radios.has(el.name)) continue;
      radios.add(el.name);
      const group = [...form.querySelectorAll(`input[type=radio][name="${CSS.escape(el.name)}"]`)];
      const legend = el.closest("fieldset")?.querySelector("legend")?.innerText || el.name;
      fields.push({ name: el.name, label: clean(legend), kind: "radio",
        required: group.some((r) => r.required) || /\*/.test(legend),
        options: group.map((r) => clean(labelOf(r))), option_values: group.map((r) => r.value),
        selector: `input[type="radio"][name="${el.name}"]` });
      continue;
    }
    const raw = labelOf(el);
    const kind = el.tagName === "SELECT" ? "select" : el.tagName === "TEXTAREA" ? "textarea"
      : ["email", "tel", "url", "file", "checkbox"].includes(type) ? type : "text";
    const opts = kind === "select" ? [...el.options] : [];
    fields.push({ name: el.name || el.id, label: clean(raw), kind, required: required(el, raw),
      options: opts.map((o) => clean(o.text)), option_values: opts.map((o) => o.value), selector: selectorOf(el) });
  }
  return fields;
}
