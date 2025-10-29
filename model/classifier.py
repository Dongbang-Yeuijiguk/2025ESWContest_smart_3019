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

# model/classifier.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import math


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 500):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, d_model)
        x = x + self.pe[:, : x.size(1)]
        return x


class TinyTransformer(nn.Module):
    def __init__(
        self,
        num_classes: int,
        input_length: int,
        d_model: int = 32,
        nhead: int = 2,
        num_layers: int = 2,
        dim_feedforward: int = 64,
    ):
        super(TinyTransformer, self).__init__()

        # 입력: (B, 1, T) → (B, T, 1)
        self.input_proj = nn.Linear(1, d_model)

        self.pos_encoder = PositionalEncoding(d_model, max_len=input_length)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=0.1,
            batch_first=True,  # (B, T, C)
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=num_layers
        )

        # 최종 분류기
        self.fc_block = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 입력 x: (B, 1, T)
        x = x.transpose(1, 2)  # (B, T, 1)
        x = self.input_proj(x)  # (B, T, d_model)
        x = self.pos_encoder(x)
        x = self.transformer_encoder(x)  # (B, T, d_model)

        # 전체 시퀀스 평균 (Global Average Pooling)
        x = x.mean(dim=1)  # (B, d_model)

        out = self.fc_block(x)
        return out
