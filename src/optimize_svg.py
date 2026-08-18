#!/usr/bin/env python3
"""Crop to A4 and optimize SVG assets for WeasyPrint PDF rendering using SVGO."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = PROJECT_ROOT / "assets" / "resume-bg.svg"
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "resume-bg-optimized.svg"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def find_svgo_command() -> list[str]:
    svgo_bin = shutil.which("svgo")
    if svgo_bin:
        return [svgo_bin]
    npx_bin = shutil.which("npx")
    if npx_bin:
        return [npx_bin, "-y", "svgo"]
    return []


def process_svg_structure(input_path: Path) -> ET.ElementTree:
    tree = ET.parse(input_path)
    root = tree.getroot()

    # Ensure A4 artbox clipPath
    defs = root.find(f".//{{{SVG_NS}}}defs")
    if defs is None:
        defs = ET.Element(f"{{{SVG_NS}}}defs")
        root.insert(0, defs)

    clip_path = defs.find(f".//{{{SVG_NS}}}clipPath[@id='page-artbox']")
    if clip_path is None:
        clip_path = ET.SubElement(defs, f"{{{SVG_NS}}}clipPath", {"id": "page-artbox"})
        ET.SubElement(clip_path, f"{{{SVG_NS}}}rect", {"id": "page-artbox-rect", "x": "0", "y": "0", "width": "210", "height": "297"})

    g_clipped = root.find(f"./{{{SVG_NS}}}g[@clip-path='url(#page-artbox)']")
    if g_clipped is None:
        children = [c for c in list(root) if not c.tag.endswith("defs")]
        wrapper = ET.Element(f"{{{SVG_NS}}}g", {"id": "page-content-wrapper", "clip-path": "url(#page-artbox)"})
        for c in children:
            root.remove(c)
            wrapper.append(c)
        root.append(wrapper)

    return tree


def optimize_svg(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT, multipass: bool = True) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input SVG not found: {input_path}")

    # Crop to A4
    tree = process_svg_structure(input_path)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        tree.write(tmp_path, encoding="utf-8", xml_declaration=True)

        # Run SVGO
        cmd_base = find_svgo_command()
        if not cmd_base:
            raise RuntimeError("Neither 'svgo' nor 'npx' was found in PATH. Please install svgo: npm install -g svgo")

        args = [*cmd_base, str(tmp_path), "-o", str(output_path)]
        if multipass:
            args.append("--multipass")

        print(f"Optimizing SVG (crop A4, SVGO): {input_path} -> {output_path}")
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"SVGO stderr: {result.stderr}", file=sys.stderr)
            raise RuntimeError(f"SVGO optimization failed with exit code {result.returncode}")

        print(result.stdout.strip())
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Crop and optimize SVG assets using SVGO.")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help="Input SVG file to optimize",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output target SVG file (default: assets/resume-bg-optimized.svg)",
    )
    parser.add_argument(
        "--no-multipass",
        action="store_true",
        help="Disable multipass optimization",
    )
    args = parser.parse_args()

    try:
        optimize_svg(input_path=args.input, output_path=args.output, multipass=not args.no_multipass)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
