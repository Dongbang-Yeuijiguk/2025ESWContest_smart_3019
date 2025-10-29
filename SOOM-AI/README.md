# SOOM-AI

## 리포지토리 역할 (Repository Role)
이 리포지토리는 SOOM 프로젝트의 AI 모델 연구 및 개발을 위한 핵심 리포지토리입니다.

Wi-Fi CSI Raw 데이터의 전처리, 증강, 시각화부터 시작하여, 1D-CNN 기반 딥러닝 모델의 학습, 평가, 결과 분석까지의 전 과정을 담당합니다. 이 리포지토리에서 개발 및 검증된 모델은 finetuning 리포지토리에서 최적화되거나 AI.Ondevice 리포지토리에서 임베디드 배포용으로 변환됩니다.

## 전체 파이프라인 (Overall Pipeline)
### 실행 방법 (How to Run)
1. 환경 설정
```
pip install -r requirements.txt
```
2. 데이터 준비
- Raw 데이터(.csv, .npy 등)를 data/ 또는 관련 폴더에 배치합니다.
- 데이터 증강이 필요한 경우, augmentation/orig_data/에 원본 데이터를 넣고 augmentation.py를 실행합니다.

3. 데이터 전처리
- script/train_data_main.py를 실행하여 preprocessed/ 폴더에 학습용 데이터를 생성합니다.

4. 모델 학습
- model/config.py 파일에서 학습 관련 하이퍼파라미터(학습률, 배치 사이즈 등)를 조정합니다.
- 아래 명령어를 통해 모델 학습을 시작합니다.
```
python model/run.py
```
5. 결과 확인
- 학습이 완료되면 results/ 디렉토리에 실행 시간별로 결과(가중치, 로그, 그래프)가 저장됩니다.
- plot_log.py를 사용하여 metrics.jsonl 파일의 학습 과정을 시각화할 수 있습니다.

### 디렉토리 구조 (Directory Structure)
```
SOOM-AI/
├── data/                             # 원본 데이터(Raw Data) 저장 폴더
├── preprocessed/                     # 전처리가 완료된 데이터가 클래스별로 저장되는 폴더
├── augmentation/                     # 데이터 증강(augmentation) 관련 코드 및 데이터 폴더
│   ├── orig_data/                    # 증강할 원본 데이터 (.npy)
│   ├── augmented_data/               # 증강된 결과 데이터가 저장되는 폴더
│   ├── augmentation.py               # 데이터 증강 실행 스크립트
│   └── visualize.py                  # 증강 데이터 시각화 스크립트
│
├── model/                            # 모델 학습 및 변환 관련 핵심 코드 폴더
│   ├── run.py                        # trainer.py를 실행하기 위한 진입점(entry point)
│   ├── trainer.py                    # 실제 모델 학습, 평가, 저장 과정을 총괄하는 메인 로직
│   ├── config.py                     # 학습률, 배치 사이즈 등 모든 하이퍼파라미터와 설정 관리
│   ├── classifier.py                 # 모델 구조(Architecture) 정의 (1D-CNN)
│   ├── preprocessed_dataloader.py    # 학습용 데이터셋 및 데이터 로더 정의
│   ├── convert_to_torchscript.py     # TorchScript 변환 스크립트
│   └── convert_to_tflite.py          # PyTorch 모델을 TFLite로 변환하는 스크립트
│
├── utils/                            # 프로젝트 전반에서 사용되는 유틸리티 함수 모음
│   ├── data_preprocessing.py         # 전체 전처리 파이프라인을 정의한 메인 유틸리티
│   ├── extract.py                    # Raw CSI 데이터에서 진폭/위상 추출
│   ├── noise_filtering.py            # DWT, Kalman Filter 등 노이즈 제거
│   ├── pca.py                        # PCA를 이용한 서브캐리어 차원 축소
│   ├── fft_filter.py                 # FFT 기반 저역 통과 필터
│   ├── breathing.py                  # FFT를 이용해 호흡수(BPM) 계산
│   ├── normalize.py, crop.py, load.py # 데이터 정규화, 로딩, 자르기 등 보조 유틸리티
│   └── visualize_signal.py           # 전처리 단계별 신호 변화 시각화
│
├── script/                           # 데이터 분석, 초기 테스트 등을 위한 독립 실행형 스크립트
│   ├── train_data_main.py            # 초기 데이터 전처리 파이프라인 실행
│   └── visualize_compare_pca.py      # PCA 적용 전후 결과 비교 시각화
│
├── results/                          # 모델 학습 시 생성되는 결과물(가중치, 로그, 그래프) 저장 폴더
└── viz_compare_pca_line/             # 데이터 시각화 결과물(.png) 저장 폴더
│
├── requirements.txt                  # 프로젝트 실행에 필요한 라이브러리 목록
├── plot_log.py                       # 학습 로그(metrics.jsonl)를 시각화하는 스크립트
└── ...
```