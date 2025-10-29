import os
import time
import argparse
from pathlib import Path
import numpy as np

from data.influx_connector import InfluxConnector
from data.preprocessing import preprocess_csi_dataframe

def fetch_and_process(
    connector: InfluxConnector,
    output_dir: Path,
    label: str,
    interval_sec: int,
    bucket: str,
    measurement: str,
):
    """지정된 시간 동안의 데이터를 가져와 전처리하고 .npy 파일로 저장합니다."""
    print(f"Fetching data for label '{label}' for the last {interval_sec} seconds...")
    df = connector.get_data(bucket, measurement, interval_sec)
    
    if df is None or df.empty:
        print(f"  -> No data found for '{label}'.")
        return 0

    # 데이터 전처리 실행
    try:
        processed_data = preprocess_csi_dataframe(df)
    except Exception as e:
        print(f"  -> Failed to preprocess data for '{label}': {e}")
        return 0

    # <output_dir>/<label>/<timestamp>.npy 형태로 저장
    label_dir = output_dir / label
    label_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(time.time() * 1000)
    output_path = label_dir / f"{timestamp}.npy"
    
    # ❗️ [중요] ❗️
    # 전처리 결과(processed_data)를 (Time, Features) 2D 배열로 저장
    # 예: (500, 1)
    # 만약 데이터 길이가 너무 길다면, 여기서 segment_2d 같은 로직으로 잘라야 합니다.
    # 지금은 (T, F) 형태의 배열 1개를 저장한다고 가정합니다.
    np.save(output_path, processed_data)
    print(f"  -> Saved preprocessed data to {output_path}")
    return 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=str, required=True, help="Preprocessed .npy files output dir")
    # InfluxDB 정보는 환경 변수로 받는 것이 안전합니다.
    args = ap.parse_args()

    INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
    INFLUX_ORG = os.environ.get("INFLUX_ORG")
    INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "csi_bucket")
    INFLUX_MEASUREMENT = os.environ.get("INFLUX_MEASUREMENT", "csi_raw")
    
    # ❗️ [자동화 로직] ❗️
    # 실제 환경에서는 이 부분을 자동화해야 합니다.
    # 지금은 예시로 '지난 1시간의 walk 데이터'를 가져옵니다.
    # Cloud Scheduler가 HTTP Payload로 {"label": "walk", "interval": 3600} 등을 전달하고
    # 이 스크립트가 그걸 파싱해서 사용하도록 수정해야 합니다.
    tasks = [
        {"label": "walk", "interval": 3600},
        {"label": "sit", "interval": 3600},
    ]

    connector = InfluxConnector(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    output_path = Path(args.output_dir)
    total_files = 0

    for task in tasks:
        files_created = fetch_and_process(
            connector, 
            output_path, 
            task["label"], 
            task["interval"], 
            INFLUX_BUCKET, 
            INFLUX_MEASUREMENT
        )
        total_files += files_created
    
    connector.close()
    print(f"Data preparation finished. {total_files} new files created.")

if __name__ == "__main__":
    main()
