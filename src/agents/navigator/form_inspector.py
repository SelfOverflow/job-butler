"""Read an application form's controls from a live page, and fill a FillPlan into it."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from src.agents.navigator.field_mapper import FieldSpec, FillPlan

_INSPECT_JS = (Path(__file__).parent / "inspect_form.js").read_text(encoding="utf-8")
StepCallback = Callable[[int, int, str, str], None]


def inspect_form(page: Page) -> list[FieldSpec]:
    raw: list[dict[str, Any]] = page.evaluate(_INSPECT_JS)
    return [
        FieldSpec(
            name=f["name"],
            label=f["label"],
            kind=f["kind"],
            required=f["required"],
            options=tuple(f["options"]),
            option_values=tuple(f["option_values"]),
            selector=f["selector"],
        )
        for f in raw
    ]


def fill_form(
    page: Page,
    plan: FillPlan,
    on_step: StepCallback | None = None,
) -> None:
    total = len(plan.planned)
    for i, item in enumerate(plan.planned, start=1):
        spec, value = item.field, item.value
        if on_step is not None:
            on_step(i, total, spec.label, spec.kind)
        if spec.kind in ("select", "radio"):
            option_value = spec.option_values[spec.options.index(value)]
            if spec.kind == "select":
                page.select_option(spec.selector, value=option_value)
            else:
                page.check(f'{spec.selector}[value="{option_value}"]')
        elif spec.kind == "checkbox":
            page.set_checked(spec.selector, value == "true")
        elif spec.kind == "file":
            page.set_input_files(spec.selector, value)
        else:
            page.fill(spec.selector, value)


def submit_form(page: Page, plan: FillPlan) -> None:
    """Click the submit control of the form that holds the planned fields, then wait."""
    anchor = plan.planned[0].field.selector
    form = page.locator(f"form:has({anchor})")
    form.locator("button[type=submit], input[type=submit], button:not([type])").first.click()
    page.wait_for_load_state("domcontentloaded")
