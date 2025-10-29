# utils/load.py
# CSI 데이터 로드 함수

def load_csi_data(file_path):
    """
    file_path: CSI 데이터가 저장된 파일 경로
    return: pd.DataFrame
    """
    import pandas as pd
    df = pd.read_csv(file_path)
    return df