from __future__ import annotations
import argparse, os, json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from sklearn.metrics import classification_report, f1_score
from tqdm import tqdm

# ❗️[변경] NPY 데이터로더 import
from datasets.preprocessed_dataset import make_preprocessed_dataloaders
from models.classifier import build_model
# ❗️[삭제] CSV 데이터셋 및 전처리 import
# from datasets.csi_dataset import CSIDataset, SegConfig
# from utils.preprocess import PreprocConfig

from utils.regularizers import L2SP
from utils.checkpoint import save_ckpt, load_ckpt
from utils.common import set_seed, save_json, load_json, now_utc_ts

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-root', type=str, required=True, help="Root dir for preprocessed .npy files")
    ap.add_argument('--out-dir', type=str, required=True)
    ap.add_argument('--base-ckpt', type=str, default=None, help="Base model checkpoint for fine-tuning")
    ap.add_argument('--resume', type=str, default=None)
    ap.add_argument('--classes', nargs='+', default=['empty','lie_down','stand_up','walk','sit'])
    ap.add_argument('--force-all', action='store_true') # ❗️이 로직은 discover_new_files와 연동

    # training
    ap.add_argument('--epochs', type=int, default=20)
    ap.add_argument('--batch-size', type=int, default=64)
    ap.add_argument('--lr', type=float, default=5e-4)
    ap.add_argument('--weight-decay', type=float, default=1e-4)
    ap.add_argument('--l2sp', type=float, default=1e-3)
    ap.add_argument('--freeze-epochs', type=int, default=2)
    ap.add_argument('--focal', action='store_true') # ❗️FocalLoss 구현 필요
    ap.add_argument('--amp', action='store_true')
    ap.add_argument('--cosine', action='store_true')
    ap.add_argument('--early-stop-patience', type=int, default=6)
    ap.add_argument('--grad-clip', type=float, default=5.0)
    ap.add_argument('--num-workers', type=int, default=4)
    ap.add_argument('--train-val-split', type=float, default=0.9)

    # ❗️[변경] 데이터 및 전처리 인자
    # On-the-fly 전처리 인자 삭제 (fs, bandpass, wavelet 등)
    # NPY 로더에 필요한 인자 추가
    ap.add_argument('--input-length', type=int, default=500, help="Input length (window size) of the model")

    return ap.parse_args()

# ❗️[변경] .csv 대신 .npy 파일을 찾도록 수정
def discover_new_files(root: Path, last_run_path: Path, force_all: bool) -> list[Path]:
    all_npy_files = sorted(list(root.rglob('*.npy')))
    if force_all or not last_run_path.exists():
        return all_npy_files
    
    meta = load_json(str(last_run_path)) or {}
    last_ts = meta.get('last_success_ts', 0)
    
    out = []
    for p in all_npy_files:
        try:
            mtime = p.stat().st_mtime
            if mtime > last_ts:
                out.append(p)
        except FileNotFoundError:
            continue # 파일이 그새 삭제된 경우
    return out

# ❗️[추가] FocalLoss (기존 코드에 있었음)
class FocalLoss(nn.Module):
    # ... (FocalLoss 구현) ...
    pass

# ❗️[추가] compute_class_weights (기존 코드에 있었음)
def compute_class_weights(labels: list[int], num_classes: int) -> torch.Tensor:
    # ... (compute_class_weights 구현) ...
    counts = np.bincount(np.array(labels), minlength=num_classes) + 1
    inv = 1.0 / counts
    w = inv / inv.sum() * num_classes
    return torch.tensor(w, dtype=torch.float32)


# ❗️[변경] train_one_epoch이 .npy 로더의 (xb, yb, _) 튜플을 받도록 수정
def train_one_epoch(model, loader, optimizer, device, scaler, criterion, l2sp_reg: L2SP | None, grad_clip: float):
    model.train()
    total_loss = 0.0
    for X, y, _ in tqdm(loader, desc='train', leave=False): # (X, y, path)
        X, y = X.to(device), y.to(device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=scaler is not None):
            logits = model(X)
            loss = criterion(logits, y)
            if l2sp_reg is not None:
                loss = loss + l2sp_reg(model)
        
        if scaler is not None:
            scaler.scale(loss).backward()
            if grad_clip > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
        total_loss += loss.item() * X.size(0)
    return total_loss / len(loader.dataset)

# ❗️[변경] evaluate가 .npy 로더의 (xb, yb, _) 튜플을 받도록 수정
def evaluate(model, loader, device, num_classes: int):
    model.eval()
    ys, ps = [], []
    with torch.no_grad():
        for X, y, _ in tqdm(loader, desc='eval', leave=False): # (X, y, path)
            X = X.to(device)
            logits = model(X)
            pred = logits.softmax(-1).argmax(-1).cpu().numpy()
            ys.extend(y.cpu().numpy()) # y가 텐서일 수 있으므로 .cpu().numpy()
            ps.extend(pred)
    
    f1 = f1_score(ys, ps, average='macro')
    report = classification_report(ys, ps, labels=list(range(num_classes)), output_dict=True, zero_division=0)
    return f1, report

# ❗️[추가] 레이어 동결 함수
def set_backbone_trainable(model: nn.Module, flag: bool):
    """모델의 Conv 레이어들을 동결/해제합니다."""
    print(f"Setting Conv blocks trainable: {flag}")
    for name, p in model.named_parameters():
        if 'conv_block' in name:
            p.requires_grad = flag

def main():
    args = parse_args()
    set_seed(42)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    last_run_path = out_dir / 'last_run.json'

    # ❗️[변경] .npy 파일 검색
    files = discover_new_files(Path(args.data_root), last_run_path, args.force_all)
    if len(files) == 0:
        print('No new .npy files found. Use --force-all to include all.'); return
    print(f"Found {len(files)} new .npy files to process.")

    # ❗️[변경] 데이터셋 로직
    class_map = {name: i for i, name in enumerate(args.classes)}
    num_classes = len(class_map)
    
    # ❗️[변경] NPY 데이터로더 생성
    dl_train, dl_val, label_names = make_preprocessed_dataloaders(
        preprocessed_root=args.data_root,
        label_map=class_map,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        seed=42,
        train_val_split=args.train_val_split,
        add_channel_dim=True,
        input_length=args.input_length
    )

    # ❗️[변경] 클래스 가중치 계산 (데이터로더에서 레이블 정보 추출 필요)
    # PreprocessedCSIDataset이 레이블 리스트를 가지고 있다면 쉽게 계산 가능
    # 지금은 임시로 생성 (정확한 계산을 위해선 ds_train.labels 접근 필요)
    labels = [label for _, label, _ in ds_train.dataset] # ❗️ds_train.dataset 접근 방식 확인 필요
    class_weights = compute_class_weights(labels, num_classes)

    # Model
    model = build_model(num_classes=num_classes, input_length=args.input_length)

    base_sd = None
    if args.base_ckpt and os.path.exists(args.base_ckpt):
        print(f"Loading base model from: {args.base_ckpt}")
        ckpt = load_ckpt(args.base_ckpt)
        # ❗️[변경] `InitialTrainer`의 체크포인트 형식('model_state')에 맞춤
        if 'model_state' in ckpt:
            model.load_state_dict(ckpt['model_state'], strict=False)
            base_sd = ckpt['model_state']
        elif 'model' in ckpt: # 기존 `FineTuner` 형식
            model.load_state_dict(ckpt['model'], strict=False)
            base_sd = ckpt['model']
        else: # state_dict만 있는 경우
            model.load_state_dict(ckpt, strict=False)
            base_sd = ckpt
    
    model.to(device)

    # ❗️[추가] 레이어 동결
    set_backbone_trainable(False)  # freeze

    optimizer = optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr, weight_decay=args.weight_decay)
    
    if args.focal:
        criterion = FocalLoss(weight=class_weights.to(device))
    else:
        criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

    scaler = torch.cuda.amp.GradScaler(enabled=(args.amp and device.type=='cuda'))

    if args.cosine:
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    else:
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=max(1,args.epochs//3), gamma=0.5)

    l2sp_reg = L2SP(base_sd, weight=args.l2sp) if base_sd is not None and args.l2sp>0 else None
    if l2sp_reg: print(f"L2SP regularization enabled with weight {args.l2sp}")

    best_f1, best_epoch = -1.0, -1
    epochs_no_improve = 0

    # ... (Resume 로직은 ❗️체크포인트 형식❗️에 맞게 수정 필요) ...

    for epoch in range(1, args.epochs+1):
        if epoch == args.freeze_epochs + 1:
            set_backbone_trainable(True)  # unfreeze
            optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
            if args.cosine:
                scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs - epoch + 1)

        train_loss = train_one_epoch(model, dl_train, optimizer, device, scaler, criterion, l2sp_reg, args.grad_clip)
        f1, report = evaluate(model, dl_val, device, num_classes)
        scheduler.step()

        print(f"Epoch {epoch}: train_loss={train_loss:.4f} val_f1={f1:.4f}")

        # ❗️[변경] 체크포인트 저장 형식을 `InitialTrainer`의 'model_state'로 통일
        save_ckpt(str(out_dir / 'last.pth'), 
                  model_state=model.state_dict(), 
                  optimizer_state=optimizer.state_dict(), 
                  scaler_state=(scaler.state_dict() if scaler is not None else None), 
                  best_f1=best_f1, best_epoch=best_epoch, epoch=epoch)

        if f1 > best_f1:
            best_f1, best_epoch = f1, epoch
            save_ckpt(str(out_dir / 'best.pth'), 
                      model_state=model.state_dict(), 
                      meta={'val_report': report, 'epoch': epoch},
                      label_names=label_names)
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= args.early_stop_patience:
                print('Early stopping.')
                break

    save_json(str(last_run_path), {'last_success_ts': now_utc_ts()})
    print(f"Best model saved with F1: {best_f1:.4f} at epoch {best_epoch}")

if __name__ == '__main__':
    main()
