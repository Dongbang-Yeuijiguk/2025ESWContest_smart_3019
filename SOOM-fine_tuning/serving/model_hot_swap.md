# Safe model hot‑swap
- Pull versioned `best_YYYYMMDD.pth`; update alias `latest.pth` atomically.
- Verify SHA‑256; keep `previous.pth` for rollback.
- Drain in‑flight requests; swap model handle; warmup.
- Canary to N% devices for 24h; promote on success.
- Rollback if error/F1‑drift exceeds threshold.
