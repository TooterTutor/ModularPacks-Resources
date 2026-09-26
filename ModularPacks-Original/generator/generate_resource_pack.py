#!/usr/bin/env python3
import json
from pathlib import Path

# Expected layout:
# ResourcePack/
# ├── assets/
# ├── pack.mcmeta
# └── modularpacks-generator/
#     ├── config.json
#     └── generate_resource_pack.py
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("config.json")
CONFIG = json.loads(CONFIG_PATH.read_text())

SLOTS = CONFIG["slots"]
MODULES = CONFIG["modules"]
COLORS = CONFIG["colors"]


def tint_array(default):
    return [
        {"type": "minecraft:custom_model_data", "index": i, "default": default}
        for i in range(6)
    ]


def make_model(model_id, default_tint=None):
    node = {
        "type": "minecraft:model",
        "model": model_id
    }

    if default_tint is not None:
        node["tints"] = tint_array(default_tint)

    return node


def make_select(slot_idx, *, back=False):
    pos = slot_idx + 1
    cases = []

    for module in MODULES:
        prefix = f"modularpacks:medallions/pos{pos}/"
        if back:
            prefix += "backmodel/"

        cases.append({
            "when": f"modularpacks.slot.{slot_idx}:{module}",
            "model": make_model(f"{prefix}pos{pos}-{module}")
        })

    return {
        "type": "minecraft:select",
        "property": "minecraft:custom_model_data",
        "index": slot_idx,
        "cases": cases,
        "fallback": {
            "type": "minecraft:empty"
        }
    }


def player_head_fallback():
    # Preserves the vanilla player-head renderer when the item does not match
    # one of ModularPacks' CustomModelData thresholds.
    return {
        "type": "minecraft:special",
        "base": "minecraft:item/template_skull",
        "model": {
            "type": "minecraft:player_head"
        },
        "transformation": {
            "left_rotation": [1.0, 0.0, 0.0, -0.0],
            "right_rotation": [0.0, 0.0, 0.0, 1.0],
            "scale": [1.0, 1.0, 1.0],
            "translation": [0.5, 0.0, 0.5]
        }
    }


def air_fallback():
    return {
        "type": "minecraft:model",
        "model": "minecraft:item/air"
    }


def make_backpack_item():
    return {
        "model": {
            "type": "minecraft:composite",
            "models": [
                make_model(
                    CONFIG["backpack_front_model"],
                    CONFIG["backpack_default_tint"]
                ),
                *[make_select(i, back=False) for i in range(SLOTS)]
            ]
        }
    }


def make_wearable_item(base_model_id, *, back=False, fallback):
    color_dispatch = {
        "type": "minecraft:range_dispatch",
        "property": "minecraft:custom_model_data",
        "index": 0,
        "entries": [
            {
                "threshold": color["threshold"],
                "model": make_model(base_model_id, color["default_tint"])
            }
            for color in COLORS
        ],
        "fallback": fallback
    }

    return {
        "model": {
            "type": "minecraft:composite",
            "models": [
                color_dispatch,
                *[make_select(i, back=back) for i in range(SLOTS)]
            ]
        }
    }


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {path.relative_to(ROOT)}")


def main():
    write_json(
        ROOT / "assets/modularpacks/items/backpack/backpack.json",
        make_backpack_item()
    )

    write_json(
        ROOT / CONFIG["minecraft_item_targets"]["player_head"],
        make_wearable_item(
            CONFIG["backpack_front_model"],
            back=False,
            fallback=player_head_fallback()
        )
    )

    write_json(
        ROOT / CONFIG["minecraft_item_targets"]["air"],
        make_wearable_item(
            CONFIG["backpack_back_model"],
            back=True,
            fallback=air_fallback()
        )
    )


if __name__ == "__main__":
    main()
