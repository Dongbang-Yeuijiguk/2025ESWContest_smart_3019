#!/usr/bin/env bash
set -euo pipefail

# ❗️[필수] InfluxDB 접속 정보. Cloud Run Job의 Secret으로 주입
: "${INFLUX_URL:?}"
: "${INFLUX_TOKEN:?}"
: "${INFLUX_ORG:?}"
: "${INFLUX_BUCKET:?}"
: "${INFLUX_MEASUREMENT:?}"

# ❗️[필수] GCS 버킷 경로
: "${OUT_GCS:?}" 
: "${BASE_CKPT_GCS:?}" # 예: gs://my-bucket/aliases/latest.pth

# 학습 파라미터 (환경 변수로 설정 가능)
EPOCHS=${EPOCHS:-20}
BATCH_SIZE=${BATCH_SIZE:-64}
LR=${LR:-5e-4}
L2SP=${L2SP:-1e-3}
FREEZE_EPOCHS=${FREEZE_EPOCHS:-2}
INPUT_LENGTH=${INPUT_LENGTH:-500}
CLASSES=${CLASSES:-"empty,lie_down,stand_up,walk,sit"}

STAMP=$(date +%Y%m%d)
WORK=/tmp/run
DATA_DIR="$WORK/data" # ❗️NPY 파일이 저장될 로컬 경로
OUT_DIR="$WORK/out"
mkdir -p "$DATA_DIR" "$OUT_DIR"

# --- 1. 데이터 준비 단계 ---
echo "--- 1. Preparing data from InfluxDB ---"
python prepare_data.py --output-dir "$DATA_DIR"
# ❗️ prepare_data.py가 레이블/인터벌을 동적으로 받도록 수정 필요
echo "-----------------------------------------"


# --- 2. 베이스 모델 다운로드 ---
echo "--- 2. Downloading base model ---"
# ❗️ GCS에서 .pth가 아닌 .pt 파일을 가져오도록 수정 (trainer.py 형식)
gsutil cp "$BASE_CKPT_GCS" "$WORK/base.pt" || true 
echo "---------------------------------"


# --- 3. 학습/파인튜닝 단계 ---
echo "--- 3. Starting fine-tuning run ---"
# ❗️[변경] train_finetune.py의 인자들
# 전처리 관련 인자(FS, BANDPASS 등) 삭제
ARGS=(
  --data-root "$DATA_DIR"
  --out-dir "$OUT_DIR"
  --base-ckpt "$WORK/base.pt"
  --epochs "$EPOCHS"
  --batch-size "$BATCH_SIZE"
  --lr "$LR"
  --l2sp "$L2SP"
  --freeze-epochs "$FREEZE_EPOCHS"
  --input-length "$INPUT_LENGTH"
  --amp
  --cosine
)
IFS=',' read -r -a CLS_ARR <<< "$CLASSES"; ARGS+=( --classes "${CLS_ARR[@]}" )

python train_finetune.py "${ARGS[@]}"
echo "-----------------------------------"


# --- 4. 결과 업로드 ---
echo "--- 4. Uploading results to GCS ---"
# ❗️ .pth 대신 .pt 파일을 업로드
BEST="$OUT_DIR/best.pt"; LAST="$OUT_DIR/last.pt"
if [ -f "$BEST" ]; then
  gsutil cp "$BEST" "$OUT_GCS/versions/best_${STAMP}.pt"
  gsutil cp "$OUT_GCS/versions/best_${STAMP}.pt" "$OUT_GCS/aliases/latest.pt"
  echo "Uploaded best model to $OUT_GCS/aliases/latest.pt"
fi
if [ -f "$LAST" ]; then 
  gsutil cp "$LAST" "$OUT_GCS/versions/last_${STAMP}.pt"
fi
echo "---------------------------------"
