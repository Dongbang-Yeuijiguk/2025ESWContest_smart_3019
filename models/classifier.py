# model/classifier.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class Simple1DCNN(nn.Module):
    def __init__(self, num_classes: int, input_length: int):
        super(Simple1DCNN, self).__init__()
        
        # 입력 형태: (배치 크기, 1, 길이) 예: (32, 1, 500)
        self.conv_block1 = nn.Sequential(
            nn.Conv1d(in_channels=1, out_channels=32, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2, stride=2)
        )
        
        self.conv_block2 = nn.Sequential(
            nn.Conv1d(in_channels=32, out_channels=64, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2, stride=2)
        )
        
        self.flatten = nn.Flatten()
        
        # Fully Connected Layer의 입력 크기를 동적으로 계산
        # (입력 길이 / 4) * 64
        dummy_input = torch.randn(1, 1, input_length)
        dummy_output = self.conv_block2(self.conv_block1(dummy_input))
        flattened_size = dummy_output.view(1, -1).size(1)

        self.fc_block = nn.Sequential(
            nn.Linear(flattened_size, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv_block1(x)
        x = self.conv_block2(x)
        x = self.flatten(x)
        x = self.fc_block(x)
        return x

def build_model(num_classes: int, input_length: int) -> nn.Module:
    return Simple1DCNN(num_classes=num_classes, input_length=input_length)
