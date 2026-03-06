# Demo Config Pack

These configs are intentionally short, visual-first runs for colleagues, students,
and website demos. They are not used for claim-making.

Pack `demo` scenarios:
- `demo_single_patch_reversal.yaml`: seasonal reversal dynamics in one patch.
- `demo_multipatch_uncoupled.yaml`: multi-patch baseline with no coupling.
- `demo_multipatch_sync_positive.yaml`: positive coupling tends toward synchrony.
- `demo_multipatch_desync_negative.yaml`: negative lagged coupling tends toward
  anti-phase/boundary behavior.

Pack `demo_v2` scenarios (stronger separation + weaker lock-in baseline):
- `demo_v2_single_patch_reversal.yaml`
- `demo_v2_multipatch_uncoupled.yaml`
- `demo_v2_multipatch_sync_positive.yaml`
- `demo_v2_multipatch_desync_negative.yaml`

Run + plot `demo` pack:

```bash
PYTHONPATH=src /Users/agabel/projects/leviathan-egg/.venv/bin/python \
  /Users/agabel/projects/leviathan-egg/scripts/demo_visual_quickstart.py
```

Run + plot `demo_v2` pack with 3-seed ribbons:

```bash
PYTHONPATH=src /Users/agabel/projects/leviathan-egg/.venv/bin/python \
  /Users/agabel/projects/leviathan-egg/scripts/demo_visual_quickstart.py \
  --pack demo_v2 \
  --seed-list 111,222,333
```

Outputs are written to:
- `experiments/runs/demo_visual/gallery/` for `demo`
- `experiments/runs/demo_visual_v2/gallery/` for `demo_v2`
  - per-scenario ribbon PNGs
  - `demo_effect_deltas_vs_uncoupled.png`
  - `demo_sync_overlay_smoothed.png`
  - `demo_gallery.md`
  - `demo_gallery_index.csv`
  - `demo_gallery_replicates.csv`

Notes:
- Keep this pack lightweight and deterministic.
- If you change demo thresholds/parameters, update this README and commit together.
