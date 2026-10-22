"""Read an application form's controls from a live page, and fill a FillPlan into it."""

from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from src.agents.navigator.field_mapper import FieldSpec, FillPlan

_INSPECT_JS = (Path(__file__).parent / "inspect_form.js").read_text(encoding="utf-8")


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


def fill_form(page: Page, plan: FillPlan) -> None:
    for item in plan.planned:
        spec, value = item.field, item.value
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
