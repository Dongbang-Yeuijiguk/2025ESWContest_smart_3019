# main_csv_test.py

import time
import config
import pandas as pd
from tqdm import tqdm
from data_source.csv_reader import CSVReader
from pipeline.inference_pipeline import InferencePipeline
from logic.sleep_state_manager import SleepStateManager

import sys
import os


class MockInfluxWriter:
    """
    A mock InfluxDB writer for testing. It mimics the real writer's methods
    but doesn't actually connect to a database.
    """
    def write_state_change(self, user_id: str, new_state: str):
        pass
    def write_result(self, **kwargs):
        pass


class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()  # 즉시 파일에 쓰도록 flush
    def flush(self):
        for f in self.files:
            f.flush()


def main_test(csv_file_path: str):
    """
    Main function for testing the pipeline with a CSV file.
    Initializes all components, including the sleep manager, and processes the file.
    """
    
    original_stdout = sys.stdout  # 나중에 복원하기 위해 원래의 표준 출력을 저장
    
    # CSV 파일 이름(확장자 제외)을 기반으로 로그 파일 이름을 생성합니다.
    # 예: SLEEP_1010.csv -> SLEEP_1010_log.txt
    base_name = os.path.splitext(os.path.basename(csv_file_path))[0]
    log_file_name = f"{base_name}_log.txt"

    try:
        # 'utf-8' 인코딩으로 로그 파일을 엽니다.
        with open(log_file_name, 'w', encoding='utf-8') as log_file:
            # sys.stdout을 Tee 클래스 인스턴스로 바꿉니다.
            # 이제부터 print()나 tqdm.write()는 모두 원래 콘솔과 log_file 양쪽에 쓰게 됩니다.
            sys.stdout = Tee(original_stdout, log_file)
            
            # --- [기존 main_test 로직 시작] ---
            # (이 안의 코드는 전혀 수정할 필요가 없습니다)
            
            print("=" * 50)
            print("🚀 Starting CSI Inference Pipeline Test with CSV File.")
            print("=" * 50)

            try:
                # --- 1. Initialize pipeline and data source ---
                print("[1/4] Initializing Inference Pipeline...")
                pipeline = InferencePipeline(config)

                print("[2/4] Initializing Sleep State Manager (with Mock Writer)...")
                mock_writer = MockInfluxWriter()
                sleep_manager = SleepStateManager(
                    user_id=config.USER_ID,
                    writer=mock_writer
                )

                timestamp_col = 'real_timestamp'
                print(f"[3/4] Pre-calculating total chunks for progress bar...")
                timestamps = pd.read_csv(csv_file_path, usecols=[timestamp_col])[timestamp_col]
                total_duration_sec = timestamps.iloc[-1] - timestamps.iloc[0]
                
                print("-" * 20)
                print(f"🕒 First Timestamp: {timestamps.iloc[0]}")
                print(f"🕒 Last Timestamp:  {timestamps.iloc[-1]}")
                print(f"⏱️ Total Duration of CSV: {total_duration_sec:.2f} seconds")
                print(f"✂️ Window Size (from config): {config.WINDOW_SECONDS} seconds")
                print("-" * 20)

                total_chunks = int((total_duration_sec - config.WINDOW_SECONDS) / config.STEP_SECONDS) + 1
                if total_chunks < 0: total_chunks = 0
                print(f"Total chunks to process: {total_chunks}")

                print(f"[4/4] Initializing CSV Reader for file: {csv_file_path}...")
                csv_reader = CSVReader(
                    file_path=csv_file_path,
                    window_sec=config.WINDOW_SECONDS,
                    step_sec=config.STEP_SECONDS,
                    timestamp_col=timestamp_col
                )

                print("\n✅ All components initialized successfully.")

            except Exception as e:
                print(f"❌ Critical error during initialization: {e}")
                return

            print("\n▶️ Starting inference process from CSV file...\n")
            start_time = time.time()

            for csi_df_chunk in tqdm(csv_reader, total=total_chunks, desc="Processing Chunks"):
                if csi_df_chunk.empty:
                    continue
                
                result = pipeline.process(csi_df_chunk)

                if result:
                    # 1. First, calculate window_start from the data chunk.
                    window_start = csi_df_chunk['real_timestamp'].min()
                    
                    # 2. Then, pass it to the sleep manager.
                    current_sleep_state = sleep_manager.update_status(result, current_timestamp=window_start)
                    
                    # The rest of the code is the same.
                    tqdm.write(
                        f"[{window_start:.2f}s] Status: {result.get('status', 'N/A')}, "
                        f"Movement: {result.get('movement', 'N/A')} (Conf: {result.get('movement_conf', 0.0):.2f}), "
                        f"SleepState: {current_sleep_state}, "
                        f"BPM: {result.get('bpm', 0.0):.2f} (Conf: {result.get('bpm_conf', 0.0):.2f})"
                    )

            end_time = time.time()
            print("\n" + "=" * 50)
            print(f"✅ CSV processing finished.")
            print(f"Processed {total_chunks} chunks in {end_time - start_time:.2f} seconds.")
            print("=" * 50)
            
            # --- [기존 main_test 로직 끝] ---

    finally:
        sys.stdout = original_stdout
        # 로그 파일 저장 위치를 콘솔에 마지막으로 알려줍니다.
        print(f"\nLog file saved to: {log_file_name}")


if __name__ == "__main__":
    CSV_FILE = "C:\\Users\\ssalt\\SOOM\\dataset\\full\\SLEEP_1010.csv"
    main_test(CSV_FILE)