import json
import pandas as pd
import matplotlib.pyplot as plt
import os

# --- [Configuration] ---
# ❗️ JSON 로그 파일 경로를 설정해주세요.
LOG_FILE_PATH = r"C:\\Users\\ssalt\\SOOM\\SOOM-AI\\results\\run_20251026-080713\\metrics.jsonl"
# ---------------------

# 한글 폰트 설정 (이전과 동일)
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    print("✅ 한글 폰트 'Malgun Gothic' 설정이 적용되었습니다.")
except:
    print("⚠️ 'Malgun Gothic' 폰트를 찾을 수 없습니다. 그래프의 한글이 깨질 수 있습니다.")


def parse_json_lines(file_path: str) -> pd.DataFrame:
    """
    JSON Lines 파일을 읽어 pandas DataFrame으로 파싱합니다.
    """
    print(f"Parsing log file: {file_path}")
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                clean_line = line.strip()
                if clean_line.endswith(','):
                    clean_line = clean_line[:-1]
                
                if clean_line:
                    data.append(json.loads(clean_line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping malformed line: {line.strip()} - Error: {e}")

    if not data:
        print("Error: No valid JSON data could be parsed from the file.")
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    # epoch 순서대로 정렬 (선택 사항이지만 그래프를 깔끔하게 만듦)
    df.sort_values(by='epoch', inplace=True)
    print(f"Successfully parsed {len(df)} epochs of data.")
    return df

# ✨ [핵심 수정] ✨: Loss와 Accuracy 그래프를 별도의 함수로 분리
def plot_loss(df: pd.DataFrame, output_filename: str):
    """Loss 그래프를 생성하고 저장합니다."""
    if df.empty or 'epoch' not in df.columns or 'val_loss' not in df.columns:
        print("Cannot generate Loss plot: DataFrame is empty or missing required columns.")
        return
        
    plt.figure(figsize=(10, 6)) # 그래프 크기 설정
    plt.plot(df['epoch'], df['train_loss'], color='tab:blue', linewidth=2, label='Training Loss')
    plt.plot(df['epoch'], df['val_loss'], color='tab:orange', linewidth=2, label='Validation Loss')
    
    # 예시 그림 스타일 적용
    plt.title('Training and Validation Loss', fontsize=14)
    
    # --- [수정] X축 레이블에 최종 값 추가 ---
    # 1. 최종 값 가져오기
    last_train_loss = df['train_loss'].iloc[-1]
    last_val_loss = df['val_loss'].iloc[-1]
    
    # 2. X축 레이블 텍스트 생성
    xlabel_text = (
        f'Epochs\n\n'
        f'Final Train Loss: {last_train_loss:.4f}  |  '
        f'Final Val Loss: {last_val_loss:.4f}'
    )
    plt.xlabel(xlabel_text, fontsize=12)
    # --- [끝] ---
    
    plt.ylabel('Loss', fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(range(int(df['epoch'].min()), int(df['epoch'].max())+1, 2)) # X축 눈금 간격 조정
    plt.ylim(bottom=0) # Y축 시작점을 0으로 설정 (선택 사항)

    # --- [제거] 기존의 그래프 위에 텍스트로 표시하는 부분 ---
    # last_epoch = df['epoch'].iloc[-1]
    # last_val_loss = df['val_loss'].iloc[-1]
    # # 그래프 끝에 텍스트로 표시
    # plt.text(last_epoch, last_val_loss, f'  Final: {last_val_loss:.4f}', 
    #          verticalalignment='center', horizontalalignment='left', color='tab:orange', fontsize=10)
    # --- [끝] ---

    # 가장 낮은 Validation Loss 지점 표시 (이전과 동일)
    min_val_loss_epoch_idx = df['val_loss'].idxmin()
    # best_epoch = df['epoch'][min_val_loss_epoch_idx]
    # min_loss = df['val_loss'][min_val_loss_epoch_idx]
    # plt.axvline(x=best_epoch, color='green', linestyle='--', 
    #             label=f'Best Epoch: {best_epoch} (Loss: {min_loss:.4f})')
    plt.legend(fontsize=11) # 범례 업데이트

    plt.tight_layout()
    plt.savefig(output_filename)
    print(f"Loss chart saved successfully to: {output_filename}")

def plot_accuracy(df: pd.DataFrame, output_filename: str):
    """Accuracy 그래프를 생성하고 저장합니다."""
    if df.empty or 'epoch' not in df.columns or 'val_acc' not in df.columns:
        print("Cannot generate Accuracy plot: DataFrame is empty or missing required columns.")
        return

    plt.figure(figsize=(10, 6)) # 그래프 크기 설정
    plt.plot(df['epoch'], df['train_acc'], 'o-', color='royalblue', label='Training Accuracy')
    plt.plot(df['epoch'], df['val_acc'], 'o-', color='firebrick', label='Validation Accuracy')

    # --- [수정] X축 레이블에 최종 값 추가 ---
    # 1. 최종 값 가져오기
    last_train_acc = df['train_acc'].iloc[-1]
    last_val_acc = df['val_acc'].iloc[-1]

    # 2. X축 레이블 텍스트 생성
    xlabel_text = (
        f'Epoch\n\n'
        f'Final Train Acc: {last_train_acc:.4f}  |  '
        f'Final Val Acc: {last_val_acc:.4f}'
    )
    plt.xlabel(xlabel_text, fontsize=12)
    # --- [끝] ---

    # --- [제거] 기존의 그래프 위에 텍스트로 표시하는 부분 ---
    # 1. 최종 값
    # last_epoch = df['epoch'].iloc[-1]
    # last_val_acc = df['val_acc'].iloc[-1]
    # plt.text(last_epoch, last_val_acc, f'  Final: {last_val_acc:.4f}', 
    #          verticalalignment='center', horizontalalignment='left', color='firebrick', fontsize=10)
    # --- [끝] ---

    # 2. 최고 값 (Loss 플롯과 통일)
    max_val_acc_epoch_idx = df['val_acc'].idxmax()
    best_epoch = df['epoch'][max_val_acc_epoch_idx]
    max_acc = df['val_acc'][max_val_acc_epoch_idx]
    plt.axvline(x=best_epoch, color='blue', linestyle='--', 
                label=f'Best Epoch: {best_epoch} (Acc: {max_acc:.4f})')
    # --- [끝] ---

    plt.title('Training and Validation Accuracy', fontsize=14)
    # plt.xlabel('Epoch', fontsize=12) # <- 위에서 수정된 xlabel_text로 대체됨
    plt.ylabel('Accuracy', fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(range(int(df['epoch'].min()), int(df['epoch'].max())+1, 2)) # X축 눈금 간격 조정
    plt.ylim(0, 1.05) # Y축 범위를 0 ~ 1.05로 설정

    plt.tight_layout()
    plt.savefig(output_filename)
    print(f"Accuracy chart saved successfully to: {output_filename}")

if __name__ == "__main__":
    if not os.path.exists(LOG_FILE_PATH):
        print(f"Error: The file '{LOG_FILE_PATH}' was not found.")
        print("Please make sure the file exists and the LOG_FILE_PATH variable is set correctly.")
    else:
        history_df = parse_json_lines(LOG_FILE_PATH)
        
        if not history_df.empty:
            # 파일 이름 설정 (Loss와 Accuracy 분리)
            base_name = os.path.splitext(LOG_FILE_PATH)[0]
            output_loss_file = f"{base_name}_loss.png"
            output_accuracy_file = f"{base_name}_accuracy.png"
            
            # ✨ [수정] ✨: 분리된 함수를 각각 호출
            plot_loss(history_df, output_loss_file)
            plot_accuracy(history_df, output_accuracy_file)

            plt.show() # 모든 그래프를 화면에 표시
        else:
            print("No data to plot.")

