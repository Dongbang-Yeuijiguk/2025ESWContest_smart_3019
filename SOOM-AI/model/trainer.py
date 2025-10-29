# model/trainer.py
from __future__ import annotations
import json, time, os, argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader

# --- 설정 파일 및 필요한 모듈 import ---
import model.config as C
from model.preprocessed_dataloader import make_preprocessed_dataloaders
from model.classifier import Simple1DCNN
from model.classifier import TinyTransformer


# ----------------------------
# 유틸리티 (Utilities)
# ----------------------------
def set_seed(seed: int = 42):
    """결과 재현을 위한 랜덤 시드를 설정합니다."""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def save_ckpt(
    path: str | Path,
    model: torch.nn.Module,
    optimizer: Optional[torch.optim.Optimizer],
    scheduler: Optional[torch.optim.lr_scheduler._LRScheduler],
    epoch: int,
    best_val_acc: float,
    label_names: List[str],
    args: object,
):
    """체크포인트를 저장합니다."""
    state_dict = model.module.state_dict() if isinstance(model, torch.nn.DataParallel) else model.state_dict()
    payload = {
        "epoch": epoch,
        "best_val_acc": best_val_acc,
        "model_state": state_dict,
        "optimizer_state": optimizer.state_dict() if optimizer is not None else None,
        "scheduler_state": scheduler.state_dict() if scheduler is not None else None,
        "label_names": label_names,
        "args": vars(args),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    torch.save(payload, path)

def load_ckpt(
    path: str | Path,
    model: torch.nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
    map_location: str | torch.device = "cpu",
) -> Dict:
    """체크포인트를 불러옵니다."""
    ckpt = torch.load(path, map_location=map_location)
    model.load_state_dict(ckpt["model_state"])
    if optimizer is not None and ckpt.get("optimizer_state") is not None:
        optimizer.load_state_dict(ckpt["optimizer_state"])
    if scheduler is not None and ckpt.get("scheduler_state") is not None:
        scheduler.load_state_dict(ckpt["scheduler_state"])
    return ckpt

# ----------------------------
# 학습 / 평가 (Train / Eval)
# ----------------------------
def train_one_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    amp: bool = True,
    grad_clip: float | None = 1.0,
) -> Tuple[float, float]:
    """1 에포크 동안 모델을 학습시킵니다."""
    model.train()
    scaler = torch.cuda.amp.GradScaler(enabled=amp)
    running_loss, running_acc, n = 0.0, 0.0, 0
    for xb, yb, _ in loader:
        xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with torch.cuda.amp.autocast(enabled=amp):
            logits = model(xb)
            loss = criterion(logits, yb)
        scaler.scale(loss).backward()
        if grad_clip and grad_clip > 0:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        scaler.step(optimizer)
        scaler.update()
        running_loss += loss.item() * xb.size(0)
        running_acc += (logits.argmax(1) == yb).float().sum().item()
        n += xb.size(0)
    return running_loss / max(1, n), running_acc / max(1, n)

@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float]:
    """데이터로더를 사용하여 모델을 평가합니다."""
    model.eval()
    running_loss, running_acc, n = 0.0, 0.0, 0
    for xb, yb, _ in loader:
        xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
        logits = model(xb)
        loss = criterion(logits, yb)
        running_loss += loss.item() * xb.size(0)
        running_acc += (logits.argmax(1) == yb).float().sum().item()
        n += xb.size(0)
    return running_loss / max(1, n), running_acc / max(1, n)

# ----------------------------
# 모델 내보내기 (Export)
# ----------------------------
def export_model(model: torch.nn.Module, loader: DataLoader, device: torch.device, exported_model_dir: Path):
    """학습된 모델을 ONNX 형식으로 내보냅니다."""
    exported_model_dir.mkdir(parents=True, exist_ok=True)
    
    # 내보내기용 예제 입력 데이터 추출
    try:
        example_input, _, _ = next(iter(loader))
        example_input = example_input[:1].to(device)
    except StopIteration:
        print("경고: 예제 입력 데이터를 찾을 수 없어 모델 내보내기를 건너뜁니다.")
        return

    m = model.module if isinstance(model, torch.nn.DataParallel) else model
    m = m.to("cpu").eval()
    example_input = example_input.to("cpu")
    
    # ONNX로 내보내기
    dynamic_axes = {"input": {0: "batch"}, "logits": {0: "batch"}} if C.ONNX_DYNAMIC_BATCH else None
    onnx_path = exported_model_dir / "model.onnx"
    try:
        torch.onnx.export(
            m, example_input, onnx_path,
            input_names=["input"], output_names=["logits"],
            opset_version=C.ONNX_OPSET, dynamic_axes=dynamic_axes,
            do_constant_folding=True
        )
        print(f"[Export] Saved ONNX to {onnx_path}")
    except Exception as e:
        print(f"ONNX 내보내기 중 오류 발생: {e}")

# ----------------------------
# 메인 학습 로직
# ----------------------------
def train_main(args):
    set_seed(C.SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # --- 경로 설정 ---
    save_dir = C.SAVE_DIR_ROOT / args.run_name
    exported_model_dir = save_dir / C.EXPORTED_MODEL_DIR_NAME
    save_dir.mkdir(parents=True, exist_ok=True)
    exported_model_dir.mkdir(parents=True, exist_ok=True)

    # --- 데이터로더 생성 ---
    dl_train, dl_val, dl_test, label_names = make_preprocessed_dataloaders(
        preprocessed_root=args.data_root, batch_size=C.BATCH_SIZE,
        num_workers=C.NUM_WORKERS, seed=C.SEED, add_channel_dim=True,
        target_labels=C.TARGET_LABELS
    )
    print(f"[Data] Loaded from: {args.data_root}")
    print(f"[Data] Target Labels: {label_names}")
    print(f"[Run] Results will be saved to: {save_dir}")

    # --- 모델, 옵티마이저, 손실 함수 등 설정 ---
    num_classes = C.NUM_CLASSES
    input_length = C.INPUT_LENGTH
    with open(save_dir / "labels.json", "w", encoding="utf-8") as f:
        json.dump({"label_names": label_names}, f, indent=2, ensure_ascii=False)

    model = Simple1DCNN(num_classes=num_classes, input_length=input_length).to(device)
    # model = TinyTransformer(num_classes=num_classes, input_length=input_length).to(device)
    if C.USE_DATA_PARALLEL and torch.cuda.device_count() > 1:
        model = torch.nn.DataParallel(model)

    criterion = nn.CrossEntropyLoss(label_smoothing=C.LABEL_SMOOTHING)
    optimizer = AdamW(model.parameters(), lr=C.LR, weight_decay=C.WEIGHT_DECAY)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=C.EPOCHS)
    
    start_epoch, best_val_acc = 1, 0.0
    
    # --- 학습 재개 또는 평가 모드 ---
    if args.resume:
        ckpt = load_ckpt(args.resume, model, None if args.eval_only else optimizer,
                         None if args.eval_only else scheduler, map_location=device)
        start_epoch = ckpt.get("epoch", 0) + 1
        best_val_acc = ckpt.get("best_val_acc", 0.0)
        print(f"[Resume] Resuming from {args.resume} (epoch {start_epoch}, best_val_acc {best_val_acc:.3f})")

    if args.eval_only:
        val_loss, val_acc = evaluate(model, dl_val, criterion, device)
        test_loss, test_acc = evaluate(model, dl_test, criterion, device)
        print(f"[EVAL] Val Loss: {val_loss:.4f}, Acc: {val_acc:.3f} | Test Loss: {test_loss:.4f}, Acc: {test_acc:.3f}")
        export_model(model, dl_val, device, exported_model_dir)
        return

    # --- 학습 루프 ---
    log_path = save_dir / "metrics.jsonl"
    patience_counter = 0

    for epoch in range(start_epoch, C.EPOCHS + 1):
        tr_loss, tr_acc = train_one_epoch(model, dl_train, criterion, optimizer, device, amp=C.USE_AMP, grad_clip=C.GRAD_CLIP)
        val_loss, val_acc = evaluate(model, dl_val, criterion, device)
        scheduler.step()

        print(f"[{epoch:03d}/{C.EPOCHS}] Train Loss: {tr_loss:.4f}, Acc: {tr_acc:.3f} | Val Loss: {val_loss:.4f}, Acc: {val_acc:.3f} | LR: {scheduler.get_last_lr()[0]:.2e}")
        
        with open(log_path, "a", encoding="utf-8") as f:
            log_entry = {"epoch": epoch, "train_loss": tr_loss, "train_acc": tr_acc, "val_loss": val_loss, "val_acc": val_acc, "lr": scheduler.get_last_lr()[0]}
            f.write(json.dumps(log_entry) + "\n")

        save_ckpt(save_dir / "last.pt", model, optimizer, scheduler, epoch, best_val_acc, label_names, args)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_ckpt(save_dir / "best.pt", model, optimizer, scheduler, epoch, best_val_acc, label_names, args)
            print(f"  -> Saved BEST model (val_acc={best_val_acc:.3f})")
            patience_counter = 0
        else:
            patience_counter += 1

        if C.PATIENCE > 0 and patience_counter >= C.PATIENCE:
            print(f"[Early Stopping] No improvement for {C.PATIENCE} epochs.")
            break

    # --- 최종 테스트 및 모델 내보내기 ---
    print("\n--- Training Finished. Testing with the best model. ---")
    if (save_dir / "best.pt").exists():
        load_ckpt(save_dir / "best.pt", model, map_location=device)
        test_loss, test_acc = evaluate(model, dl_test, criterion, device)
        print(f"[TEST] Final Loss: {test_loss:.4f}, Final Acc: {test_acc:.3f}")
        export_model(model, dl_val, device, exported_model_dir)
    else:
        print("경고: 'best.pt' 체크포인트를 찾을 수 없어 최종 테스트 및 내보내기를 건너뜁니다.")


# ----------------------------
# Argument Parser
# ----------------------------
def build_argparser():
    p = argparse.ArgumentParser(description="Train a CSI classifier on preprocessed .npy data.")
    p.add_argument("data_root", type=str, help="전처리된 .npy 파일들이 있는 루트 폴더 (예: preprocessed/)")
    p.add_argument("--run-name", type=str, default=f"run_{time.strftime('%Y%m%d-%H%M%S')}", help="이번 학습 실행의 고유 이름 (결과 폴더명으로 사용)")
    p.add_argument("--resume", type=str, default=None, help="학습을 재개할 체크포인트 파일 경로")
    p.add_argument("--eval-only", action="store_true", help="학습 없이 평가만 수행")
    return p

if __name__ == "__main__":
    args = build_argparser().parse_args()
    train_main(args)