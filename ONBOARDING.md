# Onboarding — Laser Studio UI redesign (new Ledger-styled UI)

Handoff for continuing the **new Laser Studio UI** work on another machine / agent.

## TL;DR transfer steps

1. **Get the code** — everything is committed and pushed on branch **`dev/dev`**
   (commit `8907b84`, remote `git@github.com:Ledger-Donjon/laserstudio.git`):
   ```bash
   git clone git@github.com:Ledger-Donjon/laserstudio.git
   cd laserstudio && git checkout dev/dev
   ```
   All new code, JSON schemas and the BrutGrotesque fonts are in git. Nothing
   is left uncommitted in `laserstudio/`.

2. **Recreate the venv** — the one non-obvious dependency: **pystages must come
   from the `1.4.2b` branch** (the release on PyPI does not expose `CNCError`,
   which the code imports):
   ```bash
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   .venv/bin/pip install --force-reinstall --no-deps \
     "git+https://github.com/Ledger-Donjon/pystages.git@1.4.2b"
   ```
   Verify: `.venv/bin/python -c "from pystages import CNCError; print('ok')"`.

3. **Design source** (not in git) — the redesign is driven by a claude.ai/design
   project + the Ledger Design System deck:
   - Design project id: `0710536c-1a76-4955-8b67-a36ad07e34e3`
     (file `design_handoff_workspaces/Laser Studio Refonte.dc.html` + its
     `README.md` = the authoritative spec). Access via the **DesignSync** MCP
     tool (claude.ai/design), or ask the user to copy the local
     `[OFFICIAL] Ledger Design System_Deck/` folder.
   - Design system deck id (fonts, tokens, logos):
     `official-ledger-design-system-deck-cc4b81f1-f1b1-4f5c-8d16-61bd5f41ff77`.

## What is being built

A **new UI for Laser Studio** carrying the Ledger visual identity (dark theme,
Brut Grotesque + mono, Lucide icons), running **alongside the classic dock-based
window** — both windows open at once and **share the same `Instruments`
instance** (no duplicated hardware connections). Rules the user set:

- **No emoji** anywhere in the UI (icons do that job — Lucide + Ledger logo).
- Follow the imported design **strictly**.
- Ask before implementing a feature that doesn't already exist in Laser Studio.

The window has a top bar (LASER STUDIO wordmark + workspace tabs) and 5
workspaces: **Config, Settings, Photoemission, Scan, Analyze**. Only **Config**
is implemented; the other four are placeholders that show the shared spatial
viewer.

## How to run & test

```bash
# Run the app (opens classic + new windows; loads ./config.yaml)
.venv/bin/python -m laserstudio
```

Headless smoke tests (no display) use the offscreen Qt platform — this is the
main way work was verified this session:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import sys, yaml
from PyQt6.QtWidgets import QApplication
from laserstudio.instruments.instruments import Instruments
from laserstudio.laserstudio_refonte import LaserStudioRefonte
app = QApplication(sys.argv)
cfg = yaml.safe_load(open('config.yaml'))
win = LaserStudioRefonte(Instruments(cfg), config_loaded=True, yaml_config=cfg)
print('ok', len(win._workspaces))
"
```
Expected benign errors without hardware: USB camera access denied, PDM not
found — the code degrades gracefully.

## Architecture / key files

| File | Role |
|---|---|
| `laserstudio/__main__.py` | Loads BrutGrotesque fonts, builds classic `LaserStudio` **and** `LaserStudioRefonte`, sharing `win.instruments`. Passes `config_path`, `config_loaded`, `yaml_config`. |
| `laserstudio/laserstudio_refonte.py` | New `QMainWindow`. Thin orchestrator: holds a list of `Workspace` objects, builds top-bar tabs, a left sidebar `QStackedWidget` (one panel per workspace) and a right `QStackedWidget` (shared viewer + per-workspace content). |
| `laserstudio/widgets/newui/theme.py` | Ledger design tokens (colors), shared QSS (`TAB_SS`, `GHOST_BTN`, `PURPLE_BTN`), helpers (`eyebrow`, `section_title`, `param_row`, `hline`/`vline`), and `LineSplitter` (draggable 1px handle with hover). |
| `laserstudio/widgets/newui/lucide.py` | Lucide SVG icons → `QIcon`/`QPixmap`, **HiDPI-aware** (renders at `size*devicePixelRatio`). Also `ledger_pixmap()`/`ledger_icon()` for the filled Ledger "L" logo. |
| `laserstudio/widgets/workspace/workspace.py` | `Workspace` base class: `label`, `icon`, `build_panel()` (left), `build_content()` (right; `None` = use viewer). |
| `laserstudio/widgets/workspace/{settings,photoemission,scan,analyze}workspace.py` | Thin placeholder subclasses (extension points). |
| `laserstudio/widgets/workspace/configworkspace.py` | **The bulk of the work.** Config workspace: 3 columns (project folder + file actions / instrument **tree** / editable parameter form). Editing model below. Also `InstrumentCard`, `_TreeView` (continuous connector lines), `_GridCanvas`. |
| `laserstudio/widgets/workspace/schemaform.py` | Schema-driven editable fields (`SchemaField`), interactive `ToggleSwitch`, `resolved_config_schema()` (cached, local-file resolve, no `sys.argv` mutation), `effective_properties()` (merges base props + matching `oneOf` branch by `type`). |
| `laserstudio/config_schema/*.schema.json` | JSON schemas, **corrected this session** (see below). |
| `laserstudio/fonts/BrutGrotesque-*.otf` | Ledger display font family (committed). |

## Config workspace — editing model (implemented)

Three states: **saved** (file on disk) → **working** (in-memory committed) →
**pending** (live edits in the form widgets). `file_modified = working != saved`.

- **Select** a tree node → its params show on the right as schema-driven fields.
- **Per instrument (right):** editing a field enables **Update** (commit pending
  edits into working config) and **Revert** (drop pending edits). **Delete**
  (trash) removes the instrument (list item / singleton / sub-instrument) from
  working config.
- **File level (left):** when modified, **Save** writes `config.yaml` (preserving
  the leading `# yaml-language-server` comment) then **offers a relaunch**
  (`os.execv`); **Revert** reloads working config from disk.
- The instrument **tree** nests sub-instruments (a laser's `shutter`, a camera's
  `light`) as child cards under their parent. Root card = the application
  ("Laser Studio", Ledger logo).

## Schema ↔ code audit (done) + schema fixes applied

The schemas were made to faithfully describe what the instrument code reads:
- `probe.schema.json`: added `spot_size_um`.
- `stage.schema.json`: added `num_axis` (required for Dummy), `unit_factor`
  (scalar alias), `guardrail_um`, `backlashes_um`, `shear`.
- `camera.schema.json`: added `probe_resolutions_thorough` (USB).
- `lmscontroller.schema.json`: `open_is_slidein` default → `true`.
- new `focus.schema.json` + `focussearch.schema.json`, wired into
  `config.schema.json` as `focus`.

Note: the project's `$ref` resolver (`config_generator/ref_resolve.py`) only
handles **file** refs, not intra-file `#/definitions/...` pointers — hence a
separate `focussearch.schema.json`. All example configs validate.

Known-but-not-blocking (documented, left as-is): misspelled `adresses`,
`motor`/`objective` per-subtype default mismatches.

## Next steps / not yet done

- `type` discriminator is **read-only** (changing it restructures the form via
  `oneOf` — not wired).
- Sub-instruments have **no resolved schema attached** → their fields render
  read-only. Resolve the nested sub-schema (e.g. `laser.shutter`) to make them
  editable.
- **Adding** a new instrument (the design's "ADD TO" affordance) is not built.
- Settings / Photoemission / Scan / Analyze workspaces are placeholders — see
  `design_handoff_workspaces/README.md` for their full specs (Positioning D-pad,
  scan plan + ARM LASER, emission capture + sites, results, etc.).

## Reference: the classic UI (source of truth for behavior)

`laserstudio/laserstudio.py` (classic `QMainWindow`) and
`laserstudio/instruments/` are the ground truth for what instruments read from
config. `laserstudio/config_generator/config_generator_widgets.py`
(`SchemaWidget`) is the wizard whose type→widget mapping `schemaform.py` mirrors.
