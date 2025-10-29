import torch
import torch.nn as nn

class Simple1DCNN(nn.Module):
    """
    This is the exact architecture of the trained model.
    It has been updated based on the provided classifier.py file to ensure
    that the state_dict keys match perfectly during model loading.
    """
    def __init__(self, input_length: int, num_classes: int):
        super(Simple1DCNN, self).__init__()
        
        # --- Convolutional Block 1 ---
        # As defined in the training script: out_channels=32, kernel_size=7
        self.conv_block1 = nn.Sequential(
            nn.Conv1d(in_channels=1, out_channels=32, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2, stride=2)
        )
        
        # --- Convolutional Block 2 ---
        # As defined in the training script: in_channels=32, out_channels=64
        self.conv_block2 = nn.Sequential(
            nn.Conv1d(in_channels=32, out_channels=64, kernel_size=7, stride=1, padding=3),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2, stride=2)
        )
        
        # --- Flattening Layer ---
        self.flatten = nn.Flatten()
        
        # --- Fully Connected Block ---
        # Dynamically calculate the input size for the FC layer by passing a dummy
        # tensor through the convolutional layers, just like in the training script.
        with torch.no_grad():
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

