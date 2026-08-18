#!/usr/bin/env python3
"""Render markdown resume to a PDF via Python-Markdown + WeasyPrint."""

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

import markdown
from weasyprint import HTML

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

HEADER_JSON = SCRIPT_DIR / "header.json"
HEADER_PRIVATE_JSON = SCRIPT_DIR / "header.private.json"
BODY_FILE = SCRIPT_DIR / "body.md"
STYLE_FILE = SCRIPT_DIR / "style.css"
BG_SVG = PROJECT_ROOT / "assets" / "resume-bg.svg"
DEFAULT_PDF = PROJECT_ROOT / "Rebecca Stevens - Resume.pdf"

DEFAULT_CONTACT_ORDER = ["email", "phone", "github", "linkedin"]


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Warning: Failed to load JSON from {path}: {e}")
        return {}


def format_contact_link(key: str, data: Any) -> str:
    if isinstance(data, str):
        label = data
        if key == "phone":
            href = f"tel:{re.sub(r'[^0-9+]', '', data)}"
        elif key == "email":
            href = f"mailto:{data}"
        elif data.startswith("http://") or data.startswith("https://"):
            href = data
        else:
            href = f"https://{data}"
        return f"[{label}]({href})"

    if isinstance(data, dict):
        label = data.get("label", "")
        href = data.get("href", "")
        if label and href:
            return f"[{label}]({href})"
        if label:
            return label

    return ""


def build_header_markdown(public_only: bool = False) -> tuple[str, bool]:
    header_data = load_json(HEADER_JSON)
    if not header_data:
        raise FileNotFoundError(f"Header data file not found or empty: {HEADER_JSON}")

    name = header_data.get("name", "")
    title = header_data.get("title", "")
    location = header_data.get("location", "")
    contacts = dict(header_data.get("contacts", {}))

    used_private = False
    if not public_only and HEADER_PRIVATE_JSON.exists():
        private_data = load_json(HEADER_PRIVATE_JSON)
        private_contacts = private_data.get("contacts", private_data)
        if isinstance(private_contacts, dict) and private_contacts:
            contacts.update(private_contacts)
            used_private = True

    # Order contacts canonically
    known_keys = [k for k in DEFAULT_CONTACT_ORDER if k in contacts]
    other_keys = [k for k in contacts if k not in DEFAULT_CONTACT_ORDER]
    all_keys = known_keys + other_keys

    contact_items = []
    for key in all_keys:
        link_md = format_contact_link(key, contacts[key])
        if link_md:
            contact_items.append(link_md)

    contact_line = " · ".join(contact_items)
    subtitle_line = f"**{title}** | {location}" if title and location else (f"**{title}**" if title else location)

    header_md = f"# {name}\n\n{subtitle_line}  \n{contact_line}\n"
    return header_md, used_private


def load_markdown_content(public_only: bool = False) -> tuple[str, bool]:
    if not BODY_FILE.exists():
        raise FileNotFoundError(f"Body file not found: {BODY_FILE}")

    header_md, used_private = build_header_markdown(public_only=public_only)
    body_text = BODY_FILE.read_text(encoding="utf-8")

    content = f"{header_md}\n{body_text}"
    content = re.sub(r"\\\s*$", "  ", content, flags=re.MULTILINE)
    return content, used_private


def render(output_path: Path = DEFAULT_PDF, public_only: bool = False) -> None:
    if not STYLE_FILE.exists():
        raise FileNotFoundError(f"Style file not found: {STYLE_FILE}")
    if not BG_SVG.exists():
        raise FileNotFoundError(f"Background vector artwork not found: {BG_SVG}")

    content, used_private = load_markdown_content(public_only=public_only)

    html_body = markdown.markdown(
        content,
        extensions=["tables", "fenced_code", "attr_list"],
        output_format="html5",
    )

    style_css = STYLE_FILE.read_text(encoding="utf-8")
    css_vars = f":root {{ --bg-svg: url(\"{file_uri(BG_SVG)}\"); }}"

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Rebecca Stevens – Resume</title>
  <style>
{css_vars}
{style_css}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

    HTML(string=document).write_pdf(str(output_path))
    tag = " (private build)" if used_private else " (public build)"
    print(f"Rendered: {output_path}{tag}")


def watch(output_path: Path = DEFAULT_PDF, public_only: bool = False) -> None:
    watched_files = [HEADER_JSON, HEADER_PRIVATE_JSON, BODY_FILE, STYLE_FILE, BG_SVG]
    last_mtimes: dict[Path, float] = {f: f.stat().st_mtime if f.exists() else 0.0 for f in watched_files}

    render(output_path=output_path, public_only=public_only)
    print("Watching source files for changes (Ctrl+C to stop)...")

    try:
        while True:
            time.sleep(0.5)
            changed = False
            for f in watched_files:
                current_mtime = f.stat().st_mtime if f.exists() else 0.0
                if current_mtime != last_mtimes.get(f, 0.0):
                    last_mtimes[f] = current_mtime
                    changed = True
            if changed:
                print("\n[Change detected] Re-rendering...")
                try:
                    render(output_path=output_path, public_only=public_only)
                except Exception as e:
                    print(f"Build error: {e}")
    except KeyboardInterrupt:
        print("\nStopped watch mode.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile markdown resume to PDF.")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_PDF,
        help="Target output PDF file path",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Force public build omitting private contact information",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch source files and re-render automatically on changes",
    )
    args = parser.parse_args()

    if args.watch:
        watch(output_path=args.output, public_only=args.public)
    else:
        render(output_path=args.output, public_only=args.public)


if __name__ == "__main__":
    main()