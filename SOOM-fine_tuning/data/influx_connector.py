import pandas as pd
from influxdb_client import InfluxDBClient

class InfluxConnector:
    def __init__(self, url, token, org):
        print(f"Connecting to InfluxDB... ({url})")
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.query_api = self.client.query_api()
        print("Connection to data source completed.")

    def get_data(self, bucket: str, measurement: str, interval_sec: int) -> pd.DataFrame | None:
        """
        InfluxDB에서 지정된 시간 간격만큼의 원본(raw) 데이터를 가져옵니다.
        """
        # Flux 쿼리: _time을 기준으로 real_timestamp와 data 필드를 가져옵니다.
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -{interval_sec}s)
          |> filter(fn: (r) => r._measurement == "{measurement}")
          |> filter(fn: (r) => r._field == "data" or r._field == "real_timestamp")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        try:
            df = self.query_api.query_data_frame(query=query)

            if df.empty:
                return None
            
            # 1. 불필요한 컬럼('result', 'table') 제거
            if 'result' in df.columns:
                df.drop(columns=['result'], inplace=True)
            if 'table' in df.columns:
                df.drop(columns=['table'], inplace=True)
            
            # 2. InfluxDB의 '_time' 컬럼을 DatetimeIndex로 설정
            if '_time' in df.columns:
                df.rename(columns={'_time': 'datetime_index'}, inplace=True)
                df.set_index('datetime_index', inplace=True)

            # 3. real_timestamp 컬럼을 숫자 형식으로 변환 (안정성 확보)
            if 'real_timestamp' in df.columns:
                df['real_timestamp'] = pd.to_numeric(df['real_timestamp'])
            
            return df

        except Exception as e:
            print(f"Failed to read from InfluxDB: {e}")
            return None

    def close(self):
        """DB 클라이언트 연결을 종료합니다."""
        self.client.close()
