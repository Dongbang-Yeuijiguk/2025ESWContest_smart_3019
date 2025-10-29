FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt ./
# ❗️[변경] google-cloud-storage 외 필수 라이브러리 설치
# requirements.txt에 influxdb_client, pyyaml, scikit-learn, pywt, scipy 등이 포함되어야 함
RUN pip install --no-cache-dir -r requirements.txt

# ❗️[변경] 필요한 모든 스크립트 복사
COPY . .

# ❗️ [삭제] GCS rsync는 이제 run.sh 내부의 prepare_data.py가 처리
# RUN gsutil -m rsync -r ${DATA_GCS} /app/data

ENTRYPOINT ["/bin/bash", "infra/run.sh"]
