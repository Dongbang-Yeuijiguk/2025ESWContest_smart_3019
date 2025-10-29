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
        데이터 파싱은 파이프라인에서 처리하므로, 여기서는 데이터를 그대로 전달합니다.
        
        Returns:
            pd.DataFrame: DatetimeIndex를 가지고, 'real_timestamp'와 'data' 컬럼을
                          포함하는 데이터프레임. (csv_reader와 동일한 형식)
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
            # query_data_frame은 자동으로 _time을 인덱스로 만들어주지만, 명시적으로 확인하고 설정합니다.
            if '_time' in df.columns:
                df.rename(columns={'_time': 'datetime_index'}, inplace=True)
                df.set_index('datetime_index', inplace=True)

            # 3. real_timestamp 컬럼을 숫자 형식으로 변환 (안정성 확보)
            if 'real_timestamp' in df.columns:
                df['real_timestamp'] = pd.to_numeric(df['real_timestamp'])
            
            # 최종적으로 파이프라인에 필요한 'data'와 'real_timestamp' 컬럼이 포함된 DF 반환
            return df

        except Exception as e:
            print(f"Failed to read from InfluxDB: {e}")
            return None

    def close(self):
        """DB 클라이언트 연결을 종료합니다."""
        self.client.close()