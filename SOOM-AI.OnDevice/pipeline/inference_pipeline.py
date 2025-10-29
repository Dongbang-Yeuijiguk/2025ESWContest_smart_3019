import numpy as np
import pandas as pd

# Change: Import PyTorch handler instead of TFLite handler.
from models.pytorch_handler import PyTorchModel
# from models.tflite_handler import TFLiteModel
from utils.rt_preprocess import RealtimePreprocessor
from utils.signal_processing import calculate_bpm_from_signal
from utils.extract import amp_phase_from_csi

class InferencePipeline:
    def __init__(self, config):
        print("Initializing pipeline...")
        self.config = config
        
        # Initialize utility classes
        self.preprocessor = RealtimePreprocessor(
            pca_components=config.PCA_COMPONENTS, 
            filter_ratio=config.FILTER_RATIO
        )
        
        # self.movement_model = TFLiteModel(
        #     model_path=config.MOVEMENT_MODEL_PATH, 
        #     input_length=config.MODEL_INPUT_SIZE, 
        #     num_classes=len(config.MOVEMENT_LABELS)
        # )
        
        self.movement_model = PyTorchModel(
            model_path=config.MOVEMENT_MODEL_PATH_PT, 
            input_length=config.MODEL_INPUT_SIZE, 
            num_classes=len(config.MOVEMENT_LABELS)
        )
        
        print("Pipeline initialization complete.")

    def _calculate_bpm(self, signal_1d: np.ndarray) -> dict:
        """Calculates BPM from the resampled 1D signal."""
        return calculate_bpm_from_signal(
            signal_1d,
            sampling_rate=self.config.SAMPLING_RATE,
            min_freq=self.config.BPM_MIN_FREQ,
            max_freq=self.config.BPM_MAX_FREQ
        )

    def process(self, raw_csi_df: pd.DataFrame) -> dict | None:
        """
        Runs the entire inference pipeline for the raw input DataFrame.
        It now handles CSI string parsing internally.
        """
        try:
            # 1. CSI 데이터 파싱 (52개 서브캐리어 진폭 추출)
            amp_matrix, _ = amp_phase_from_csi(raw_csi_df, column=self.config.RAW_CSI_COLUMN)

            if amp_matrix.shape[0] == 0:
                return None

            # 평균을 내지 않고, 52개 채널 데이터를 리스트 형태로 변환합니다.
            # 전처리기는 각 행에 배열이 들어있는 형태를 기대합니다.
            amplitude_list = [row for row in amp_matrix]
            
            # 52개 채널 데이터를 그대로 담는 DataFrame을 생성합니다.
            csi_df = pd.DataFrame({
                'timestamp': raw_csi_df.index,
                'amplitude': amplitude_list
            })
            
            csi_df.dropna(inplace=True)
            
            if csi_df.empty:
                return None

            # 타임스탬프를 datetime에서 숫자(Unix timestamp)로 변환합니다.
            if pd.api.types.is_datetime64_any_dtype(csi_df['timestamp']):
                csi_df['timestamp'] = csi_df['timestamp'].astype(np.int64) / 1e9

            # 2. 전처리 (리샘플링, DWT, 정규화, PCA, 필터링)
            # 이제 전처리기는 52개 채널 데이터를 받아 정상적으로 처리합니다.
            preprocessed_signal = self.preprocessor.run(csi_df, self.config.MODEL_INPUT_SIZE)
        
        except Exception as e:
            print(f"Error: Data processing or parsing failed - {e}")
            import traceback
            traceback.print_exc() # 더 자세한 에러 로그를 보기 위해 추가
            return None
        
        # 3. 존재 여부 탐지 (분산 기반)
        signal_variance = np.var(preprocessed_signal)
        is_present = signal_variance > self.config.PRESENCE_VARIANCE_THRESHOLD

        if not is_present:
            return {"status": "empty", "movement": "none", "movement_conf": 1.0, "bpm": 0.0, "bpm_conf": 0.0}

        # 4. 병렬 처리 (존재할 경우)
        # 4-1. 움직임 추론
        prediction_probabilities = self.movement_model.predict(preprocessed_signal)[0]
        confidence_score = np.max(prediction_probabilities)
        predicted_index = np.argmax(prediction_probabilities)

        if confidence_score >= self.config.MOVEMENT_CONFIDENCE_THRESHOLD:
            movement_label = self.config.MOVEMENT_LABELS[predicted_index]
        else:
            movement_label = "UNKNOWN"
        
        # 4-2. BPM 계산
        bpm_result = self._calculate_bpm(preprocessed_signal)

        # 5. 최종 결과 종합
        final_result = {
            "status": "present",
            "movement": movement_label,
            "movement_conf": float(confidence_score),
            "bpm": bpm_result.get("bpm"),
            "bpm_conf": bpm_result.get("bpm_conf"),
            "ok": bpm_result.get("ok")
        }
        return final_result