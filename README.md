# SOOM-AI.fine_tuning
> CSI Movement Detection – Periodic Fine‑Tuning

## Quickstart

```bash
python -m pip install -r requirements.txt

# dry run: show which files will be picked up for training
python train_finetune.py   --data-root /path/to/new_csi_csvs   --base-ckpt /path/to/base_resnet18.pth   --out-dir runs/exp1   --dry-run

# actual fine‑tune
python train_finetune.py   --data-root /path/to/new_csi_csvs   --base-ckpt /path/to/base_resnet18.pth   --out-dir runs/exp1   --epochs 20 --batch-size 64 --lr 5e-4 --l2sp 1e-3   --window 500 --stride 250   --bandpass 0.1 0.5 --fs 100   --dwt-denoise --wavelet db4   --mrc-pca --pca-k 1   --classes empty lie_down stand_up walk sit
```

### Data assumption
- Each **CSV** contains raw CSI frames for a session and we derive **amplitude** and shape it to (T,F) with F=52 (or 64). Provide `--fs` for Hz.
- Labels are given by a parallel **meta JSON/CSV** or via filename conventions (e.g., `.../walk_2025-09-21_123000.csv`). You can customize label extraction in `datasets/csi_dataset.py:get_label_from_path`.
- The trainer only consumes **new files** since the last successful run (tracked at `out_dir/last_run.json`). Pass `--force-all` to include everything.

### Checkpoints
- `best.pth`: best val macro‑F1
- `last.pth`: last epoch
- You can resume with `--resume runs/exp1/last.pth`.

### Tips
- To freeze early layers first: `--freeze-epochs 2`
- For stronger drift resistance, increase `--l2sp`.
- If labels are noisy, try `--focal`.
