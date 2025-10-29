# SOOM-FE.dashboard

React 기반 Enact 구조와 Sandstone 테마를 적용한 스마트홈 대시보드로,
비접촉 감지 수면 데이터를 시각화하고, 실내 환경 모니터링·기기 제어·자동화 루틴 설정을 통합 제공합니다.
사용자는 직관적인 UI를 통해 수면 리포트를 확인하고, 수면 환경을 분석 및 관리할 수 있습니다.

---

### 목차
1. [개요](#개요)  
2.	[주요 기능](#주요-기능)
3.	[구성 및 UI](#구성-및-ui)
4.	[통신 방식](#통신-방식)
5.	[기술 스택](#기술-스택)
6.	[프로젝트 파일 구조](#프로젝트-파일-구조)

---

### 개요

SOOM Dashboard는 비접촉 수면 감지 시스템과 스마트홈 기기 제어 기능을 결합한 통합 대시보드입니다.  
React 기반 Enact 구조로 구현되어 webOS 환경에 최적화되어 있으며,  
실시간 센서 데이터(WebSocket)와 수면 리포트(REST API)를 시각화하여  
사용자가 자신의 수면 패턴과 환경을 한눈에 확인하고 관리할 수 있도록 돕습니다.  

---

### 주요 기능

- **Environment Monitor**  
  온도, 습도, 공기질, 미세먼지 등 실내 환경 데이터를 실시간으로 수신하고 시각화합니다.  
  온도, 습도는 실시간 상태값을 보여주고,
  공기질, 미세먼지는 센서 값을 라벨링하여 제공합니다.

- **Sleep Report**  
수면 시간, 뒤척임, 호흡 등 데이터를 분석하여 수면 점수를 내고, 일정 기간 내의 수면 점수를 보여줍니다.

- **Report Modal System**  
수면 시간, 뒤척임, 호흡 등 항목별 상세 데이터를 모달 형태로 분리하여 사용자 친화적인 UI로 제공합니다.

- **Smart Device Control**  
조명, 커튼, 에어컨, 공기청정기 등의 스마트 기기를 대시보드 내에서 직접 제어할 수 있습니다.  
Node-RED를 통해 실시간 명령을 전송하며, 제어 결과를 즉시 UI에 반영합니다.  

- **Automation Routine**  
취침/기상 시 자동으로 수행될 루틴을 설정할 수 있습니다.  
예: 취침 시 조명 OFF + 커튼 닫기, 기상 시 조명 100% ON + 공기청정기 작동 + 커튼 열기  

---

### 구성 및 UI

1. **Dashboard Overview**  
     <img width="486" height="271" alt="스크린샷 2025-10-29 오전 3 45 58" src="https://github.com/user-attachments/assets/6e5e3c33-3681-4de7-b253-4ef82ed8be56" />

SOOM Dashboard의 메인 화면으로, 수면 리포트·실내 환경·스마트홈 제어 정보를 한눈에 확인할 수 있는 중심 UI입니다.  
사용자가 필요한 정보를 즉시 파악할 수 있도록 카드형 인터페이스로 시각화했습니다.

- **수면 리포트(Sleep Report)** : 오늘의 수면 점수, 수면 시간, 뒤척임, 평균 호흡 상태를 종합적으로 표시하며, 주간 그래프를 통해 수면 점수를 시각적으로 보여줍니다.
- **실내 환경(Environment Status)** : 온도, 습도, 공기질(AQI), 미세먼지의 센서 데이터를 실시간으로 수신하여 표시합니다. 감지된 공기질 수치가 건강에 유해할 정도이면 경고 팝업과 함께 스마트 기기가 자동 제어됩니다.
- **스마트홈 제어(Smart Home Control)** : 조명, 커튼, 에어컨, 공기청정기 등의 스마트 기기를 대시보드에서 직접 제어할 수 있습니다. 각 기기의 상태는 즉시 반영됩니다.
<br>

2. **수면 리포트(Sleep Report)**  
<img width="498" height="248" alt="image" src="https://github.com/user-attachments/assets/764c8b03-17a5-4398-bd45-7bd2f2c46b10" />

수면 리포트는 사용자의 수면 데이터를 분석해 점수, 수면 시간, 뒤척임, 호흡 상태를 시각적으로 보여주는 화면입니다.  
주간 수면 패턴을 그래프로 표시하고 일간 수면 결과를 요약하여 코멘트로 제시하며, 하단에는 주요 수면 지표가 카드 형태로 요약됩니다.

- **주간 수면 그래프(Weekly Sleep Chart)** : 날짜별 수면 시간 구간(취침–기상)을 막대 그래프로 표현하며, 각 항목의 우측에는 수면 점수가 표시됩니다.
- **일간 수면 분석 카드(Sleep Analysis)** : 오늘의 수면 점수와 평가(좋음/보통/주의)를 시각적으로 표시하며, 수면 시간, 뒤척임, 호흡 리듬 안정도 등 종합 분석 결과를 함께 제공합니다.
- **수면 지표 카드(Sleep Metrics)**
  - 수면 시간(Duration): 일간/주간/월간 평균 수면 시간 표시  
  - 뒤척임(Toss): 뒤척임 시간대 및 횟수 표시  
  - 호흡(Respiration): 평균 호흡수, 무호흡 횟수 등 수면 중 호흡 상태 표시
<br>
 
3. **자동화 루틴 설정(Automation Routine)**  
  <img width="487" height="277" alt="스크린샷 2025-10-29 오전 3 58 37" src="https://github.com/user-attachments/assets/2972fe8e-efeb-4164-aca0-5d8e3a86bace" />

 자동화 루틴 설정을 통해 기상/취침 시 실행될 루틴을 사용자가 직관적으로 자유롭게 설정합니다.  
 루틴 실행 여부, 기기 상세 조정, 기상/취침 시간 설정, 기상/취침 알림 여부 및 재알림 시간을 설정할 수 있습니다.  
 <br>

4. **스마트홈 제어(Smart Home Control)**
<table>
  <tr>
    <td><img width="291" height="162" alt="image" src="https://github.com/user-attachments/assets/6c1068ad-c18c-475a-b366-0d2b8d9e256d"/>
</td>
    <td><img width="294" height="142" alt="image" src="https://github.com/user-attachments/assets/d64846dd-6bae-4479-a0f9-3fcc64410d7b" />
</td>
  </tr>
  <tr>
    <td><img width="291" height="138" alt="image" src="https://github.com/user-attachments/assets/860fe616-f6a7-4e8d-836d-a11a3bc2800a" />
</td>
    <td><img width="291" height="138" alt="image" src="https://github.com/user-attachments/assets/9b6cce97-88a1-4583-89a7-43486d37bba0" />
</td>
  </tr>
</table>

조명, 커튼, 에어컨, 공기청정기 등 주요 기기를 카드형 인터페이스로 표시하며,  
상세 설정 창을 통해 밝기, 색온도, 커튼의 개폐, 실내 온도 및 바람 세기 설정, 공기청정기 세기 설정 등 세부 옵션을 직접 조정할 수 있습니다.  
<br>

---

### 통신 방식

- **데이터 통신 (WebSocket)**  
실내 환경 센서 데이터(온도, 습도, 공기질, 미세먼지 등)는 백엔드 서버로부터 WebSocket을 통해 실시간으로 수신됩니다.  
이를 통해 사용자는 환경 변화에 즉각적으로 반응할 수 있으며, 대시보드 화면의 지표가 주기적인 새로고침 없이 자동으로 갱신됩니다.  

- **제어 및 리포트 통신 (HTTP REST API)**  
스마트홈 기기 제어 명령과 수면 리포트 데이터는 HTTP 통신(REST API)를 통해 주고받습니다.  
사용자가 대시보드에서 스마트 기기를 조작 하면 해당 명령이 HTTP POST 요청으로 전송되어 FastAPI와 Node-RED를 거쳐 처리됩니다.  
또한 수면 리포트에 쓰이는 데이터는 HTTP GET 요청을 통해 불러오며, 분석 결과를 대시보드에 시각적으로 표시합니다.  

---

### 기술 스택

- **프레임워크**: React 기반 Enact 구조 (Sandstone 테마 적용)
- **모니터링 및 제어**: 온습도 센서, 공기질 센서, 커튼 센서 (실내 환경 모니터링)
- **통신 프로토콜**: WebSocket, HTTP
- **빌드 도구**: Vite (경량 개발 및 빌드 환경)
- **실행 환경** : webOS OSE (Raspberry Pi 4)

---

### 프로젝트 파일 구조

```plaintext
SOOM-FE.dashboard
├── .env                            # WebSocket 및 API 주소 등 환경 변수 설정 파일
├── .gitignore                      # Git 커밋 시 제외할 파일/폴더 목록
├── package-lock.json               # npm 의존성 버전 고정 파일
├── package.json                    # 프로젝트 설정 및 스크립트 정의 파일
├── README.md                       # 프로젝트 설명 문서
└── src
    ├── api
    │   ├── deviceControl.js        # 스마트홈 기기 제어 요청 (조명, 커튼, 에어컨 등)
    │   ├── nr_api.js               # Node-RED 연동 및 자동화 루틴 처리용 API
    │   └── sleep.js                # 수면 리포트 데이터(수면 시간, 호흡, 뒤척임 등) 요청 API
    ├── assets                      # 아이콘, 폰트 등 정적 리소스 폴더
    ├── components
    │   ├── Page.js                 # 공통 페이지 레이아웃 컴포넌트
    │   └── SleepChart.js           # 수면 데이터 시각화 차트 컴포넌트
    ├── hooks
    │   └── useEnvSocket.js         # 실시간 환경 데이터(WebSocket) 수신 훅
    ├── index.js                    # React 앱의 진입점 (렌더링 시작 위치)
    ├── theme
    ├── utils
    │   ├── postRoutine.js          # 자동화 루틴 설정값을 백엔드로 전송하는 유틸리티
    │   └── routinePayload.js       # 루틴 데이터를 포맷팅하여 전송 형식으로 변환하는 유틸리티
    └── views
        ├── Dashboard.js            # SOOM의 메인 대시보드 화면 (환경/수면/제어 통합 표시)
        ├── MainPanel.js            # webOS 전용 패널 루트 컴포넌트
        ├── SleepReport             # 수면 리포트 관련 모듈
        │   ├── Card
        │   │   ├── FactorCard.js   # 수면 리포트의 주요 지표(시간, 호흡, 뒤척임) 카드
        │   │   └── modals          # 수면 세부 항목 모달 UI 모음
        │   │       ├── DurationModal.js    # 수면 시간 시각화 모달
        │   │       ├── RespirationModal.js # 호흡 상태 시각화 모달
        │   │       ├── TossModal.js        # 뒤척임 빈도 시각화 모달
        │   │       └── BaseModal.js        # 모달 공통 레이아웃 컴포넌트
        │   └── SummarySection
        │       ├── SleepComment.js         # 수면 점수별 코멘트 및 피드백 문구
        │       └── WeeklyBarChart.js       # 주간 수면 시간/점수 막대그래프
        └── parts
            ├── EnvCard.js                  # 실내 환경 데이터(온도·습도·공기질 등) 카드
            ├── SmartHomeControlCard.js     # 스마트홈 기기 제어 UI 카드
            ├── AutomationPanel.js          # 자동화 루틴 설정 패널
            ├── SleepReportCard.js          # 요약 수면 리포트 카드 (메인 대시보드용)
            └── AirQualityAlertModal.js     # 공기질 상태 경고 모달 (주의 알림창) 
```
