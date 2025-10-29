import time
import config

# Import core classes from each module.
from data_source.influx_connector import InfluxConnector
from pipeline.inference_pipeline import InferencePipeline
from result_sink.influx_writer import InfluxWriter
from logic.sleep_state_manager import SleepStateManager

def main():
    """
    Main execution function.
    Initializes all components and runs the real-time inference loop.
    """
    print("=" * 50)
    print("🚀 Starting Real-time CSI Inference and Sleep State Determination System.")
    print("=" * 50)

    writer = None # Pre-declare for use in the finally block
    try:
        # --- 1. Initialize all components ---
        print("[1/4] Connecting to Data Source (InfluxDB Reader)...")
        connector = InfluxConnector(
            url=config.INFLUX_READ_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_READ_ORG
        )

        print("[2/4] Initializing Inference Pipeline...")
        pipeline = InferencePipeline(config)

        print("[3/4] Connecting to Result Sink (InfluxDB Writer)...")
        writer = InfluxWriter(
            url=config.INFLUX_WRITE_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_WRITE_ORG
        )
        
        print("[4/4] Initializing Sleep State Manager...")
        # ✨ [중요] ✨: CSV 테스트에서 수정한 최종 버전의 SleepStateManager를 사용해야 합니다.
        sleep_manager = SleepStateManager(
            user_id=config.USER_ID,
            writer=writer
        )

        print("\n✅ All components initialized successfully.")

    except Exception as e:
        print(f"❌ Critical error during initialization: {e}")
        print("Please check the DB connection info or model path in the config.py file.")
        return

    print("\n▶️ Starting real-time inference loop. (Press Ctrl+C to exit)\n")
    try:
        while True:
            loop_start_time = time.time()

            # --- 2. Fetch data ---
            # config.WINDOW_SECONDS (예: 4초) 만큼의 데이터를 가져옵니다.
            # 루프는 config.STEP_SECONDS (예: 2초) 마다 돌므로, 2초만큼 겹치는 슬라이딩 윈도우가 구현됩니다.
            csi_df = connector.get_data(
                bucket=config.INFLUX_READ_BUCKET,
                measurement=config.INFLUX_READ_MEASUREMENT,
                interval_sec=int(config.WINDOW_SECONDS)
            )

            if csi_df is None or csi_df.empty:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] No new data from InfluxDB. Waiting...")
                time.sleep(config.STEP_SECONDS)
                continue

            # --- 3. Execute pipeline ---
            result = pipeline.process(csi_df)

            # --- 4. Process results ---
            if result:
                # 데이터의 타임스탬프를 SleepStateManager에 전달합니다.
                # InfluxDB에서 온 데이터의 인덱스는 DatetimeIndex입니다.
                current_data_timestamp = csi_df.index.min().timestamp()
                current_sleep_state = sleep_manager.update_status(result, current_timestamp=current_data_timestamp)

                # 4-2. 콘솔에 결과 출력
                current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                print(
                    f"[{current_time_str}] Status: {result.get('status', 'N/A')}, "
                    f"Movement: {result.get('movement', 'N/A')} (Conf: {result.get('movement_conf', 0.0):.2f}), "
                    f"SleepState: {current_sleep_state}, "
                    f"BPM: {result.get('bpm', 0.0):.2f} (Conf: {result.get('bpm_conf', 0.0):.2f})"
                )

                # 4-3. AI 추론 결과를 InfluxDB에 저장
                writer.write_result(
                    result=result
                )
            else:
                # 추론 결과가 없을 때 로그를 남깁니다.
                current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{current_time_str}] Data chunk processed, but no valid result was generated (e.g., insufficient data).")


            # --- 5. 루프 주기 조절 ---
            elapsed_time = time.time() - loop_start_time
            sleep_time = max(0, config.STEP_SECONDS - elapsed_time)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\n👋 Program terminated normally by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error during execution: {e}")
    finally:
        if writer:
            writer.close()
        if 'connector' in locals() and connector:
            connector.close()
        print("Shutting down the system.")


if __name__ == "__main__":
    main()