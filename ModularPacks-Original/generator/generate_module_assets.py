#!/usr/bin/env python3
"""Generate missing ModularPacks medallion model declarations from config.json.

Expected layout:

ResourcePack/
├── assets/
└── modularpacks-generator/
    ├── config.json
    ├── generate_resource_pack.py
    └── generate_module_assets.py

By default this script creates only missing JSON model declarations and reports
missing PNG textures. Pass --placeholders to copy module_template.png for any
missing module textures.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "config.json"

RESOURCE_NAME = re.compile(r"^[a-z0-9._-]+$")


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Could not find config: {CONFIG_PATH}")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    if "modules" not in config or not isinstance(config["modules"], list):
        raise ValueError('config.json must contain a "modules" array')
    if "slots" not in config or not isinstance(config["slots"], int):
        raise ValueError('config.json must contain an integer "slots" value')
    if config["slots"] < 1:
        raise ValueError('"slots" must be at least 1')

    return config


def validate_modules(modules: list[str]) -> None:
    bad = [m for m in modules if not isinstance(m, str) or not RESOURCE_NAME.fullmatch(m)]
    if bad:
        raise ValueError(
            "Invalid module names in config.json: " + ", ".join(map(repr, bad)) +
            ". Use lowercase resource-location-safe names: a-z, 0-9, _, -, ."
        )


def model_definition(namespace: str, slot: int, module: str, *, back: bool) -> dict:
    pos = slot + 1
    parent_suffix = f"pos{pos}-backmodel" if back else f"pos{pos}"
    module_texture = f"{namespace}:item/medallions/{module}"

    return {
        "parent": f"{namespace}:medallions/pos{pos}/{parent_suffix}",
        "textures": {
            "0": module_texture,
            "1_0": module_texture,
            "frame": f"{namespace}:item/medallions/frame",
            "backpack": f"{namespace}:item/backpack/backpack-grayscale",
        },
    }


def write_json(path: Path, data: dict, *, force: bool, dry_run: bool) -> str:
    if path.exists() and not force:
        return "existing"

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return "overwritten" if path.exists() and force else "created"


def create_declarations(
    namespace: str,
    modules: list[str],
    slots: int,
    *,
    force: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    model_root = ROOT / "assets" / namespace / "models" / "medallions"
    created = 0
    overwritten = 0
    existing = 0

    for module in modules:
        for slot in range(slots):
            pos = slot + 1

            front_path = model_root / f"pos{pos}" / f"pos{pos}-{module}.json"
            back_path = model_root / f"pos{pos}" / "backmodel" / f"pos{pos}-{module}.json"

            for path, back in ((front_path, False), (back_path, True)):
                already_existed = path.exists()
                result = write_json(
                    path,
                    model_definition(namespace, slot, module, back=back),
                    force=force,
                    dry_run=dry_run,
                )

                if result == "existing":
                    existing += 1
                elif already_existed and force:
                    overwritten += 1
                    print(f"OVERWRITE {path.relative_to(ROOT)}")
                else:
                    created += 1
                    prefix = "WOULD CREATE" if dry_run else "CREATE"
                    print(f"{prefix} {path.relative_to(ROOT)}")

    return created, overwritten, existing


def handle_textures(
    namespace: str,
    modules: list[str],
    *,
    placeholders: bool,
    placeholder_name: str,
    dry_run: bool,
) -> tuple[list[str], int]:
    texture_root = ROOT / "assets" / namespace / "textures" / "item" / "medallions"
    missing = []
    placeholders_created = 0

    for module in modules:
        texture = texture_root / f"{module}.png"
        if not texture.exists():
            missing.append(module)

    if not placeholders or not missing:
        return missing, placeholders_created

    placeholder_source = texture_root / placeholder_name
    if not placeholder_source.is_file():
        raise FileNotFoundError(
            f"Placeholder source does not exist: {placeholder_source}\n"
            "Use --placeholder-source <file.png> or add the template texture first."
        )

    for module in missing:
        target = texture_root / f"{module}.png"
        prefix = "WOULD COPY" if dry_run else "COPY"
        print(f"{prefix} {placeholder_source.name} -> {target.relative_to(ROOT)}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(placeholder_source, target)
        placeholders_created += 1

    return missing, placeholders_created


def regenerate_item_definitions(dry_run: bool) -> None:
    generator = SCRIPT_DIR / "generate_resource_pack.py"
    if not generator.is_file():
        raise FileNotFoundError(
            f"Could not find sibling item generator: {generator}"
        )

    if dry_run:
        print(f"WOULD RUN {generator.name}")
        return

    print(f"RUN {generator.name}")
    subprocess.run([sys.executable, str(generator)], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate missing medallion model declarations for every module listed "
            "in the ModularPacks generator config."
        )
    )
    parser.add_argument(
        "--placeholders",
        action="store_true",
        help=(
            "Copy a placeholder PNG for modules whose medallion texture is missing. "
            "Existing textures are never overwritten."
        ),
    )
    parser.add_argument(
        "--placeholder-source",
        default="module_template.png",
        help="Filename inside textures/item/medallions to use with --placeholders (default: module_template.png).",
    )
    parser.add_argument(
        "--force-models",
        action="store_true",
        help="Overwrite existing generated medallion JSON declarations.",
    )
    parser.add_argument(
        "--regenerate-items",
        action="store_true",
        help="Run generate_resource_pack.py after module assets are processed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing any files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        config = load_config()
        modules = config["modules"]
        slots = config["slots"]
        namespace = config.get("namespace", "modularpacks")

        if not RESOURCE_NAME.fullmatch(namespace):
            raise ValueError(f"Invalid namespace: {namespace!r}")
        validate_modules(modules)

        created, overwritten, existing = create_declarations(
            namespace,
            modules,
            slots,
            force=args.force_models,
            dry_run=args.dry_run,
        )

        missing_textures, placeholders_created = handle_textures(
            namespace,
            modules,
            placeholders=args.placeholders,
            placeholder_name=args.placeholder_source,
            dry_run=args.dry_run,
        )

        if args.regenerate_items:
            regenerate_item_definitions(args.dry_run)

        print("\nSummary")
        print(f"  Modules in config:       {len(modules)}")
        print(f"  Slots:                   {slots}")
        print(f"  Model files created:     {created}")
        print(f"  Model files overwritten: {overwritten}")
        print(f"  Model files unchanged:   {existing}")
        print(f"  Missing textures:        {len(missing_textures)}")
        print(f"  Placeholders created:    {placeholders_created}")

        if missing_textures:
            print("\nModules still needing real medallion artwork:")
            for module in missing_textures:
                print(f"  - {module}.png")

            if not args.placeholders:
                print("\nTip: rerun with --placeholders to copy module_template.png as temporary artwork.")

        if not args.regenerate_items:
            print("\nAfter updating config/modules, run generate_resource_pack.py as well")
            print("so backpack.json, player_head.json, and air.json include the new module cases.")

        return 0

    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
