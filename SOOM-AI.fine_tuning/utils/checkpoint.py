from __future__ import annotations
import os, torch

def save_ckpt(path: str, **state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(state, path)


def load_ckpt(path: str) -> dict:
    return torch.load(path, map_location='cpu')
