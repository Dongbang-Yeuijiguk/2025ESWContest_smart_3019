from __future__ import annotations
import torch
from torch import nn

class L2SP:
    """L2‑SP: penalty to keep fine‑tuned weights close to base weights.
    Ref: Xuhong Li et al., ECCV 2018.
    """
    def __init__(self, base_state_dict: dict[str, torch.Tensor], weight: float = 1e-3):
        self.base = {k: v.clone().detach() for k, v in base_state_dict.items()}
        self.weight = weight

    def __call__(self, model: nn.Module) -> torch.Tensor:
        loss = 0.0
        for name, p in model.named_parameters():
            if not p.requires_grad:
                continue
            if name in self.base:
                loss = loss + (p - self.base[name]).pow(2).sum()
        return self.weight * loss
