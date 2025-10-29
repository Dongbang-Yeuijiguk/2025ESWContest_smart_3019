import torch
import numpy as np
from models.model_arch import Simple1DCNN 

class PyTorchModel:
    """Handles loading a PyTorch .pt model file and performing inference."""
    def __init__(self, model_path: str, input_length: int, num_classes: int):
        """
        Loads the model and sets it to evaluation mode.
        Uses GPU if available.
        """
        print(f"Loading PyTorch model from: {model_path}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device for inference: {self.device}")
        
        try:
            # Load the entire checkpoint file
            checkpoint = torch.load(model_path, map_location=self.device)
            
            # Instantiate the model architecture
            self.model = Simple1DCNN(
                input_length=input_length, 
                num_classes=num_classes
            ).to(self.device)

            # --- Corrected State Dict Loading Logic ---
            # Check for common keys where model weights are stored in checkpoints.
            # The error log indicates the correct key is 'model_state'.
            if isinstance(checkpoint, dict) and 'model_state' in checkpoint:
                self.model.load_state_dict(checkpoint['model_state'])
            elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                self.model.load_state_dict(checkpoint['model_state_dict'])
            elif isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
                 self.model.load_state_dict(checkpoint['state_dict'])
            else:
                # Fallback for when the file is the state_dict itself.
                self.model.load_state_dict(checkpoint)

            # Set the model to evaluation mode
            self.model.eval()
            print("PyTorch model loaded successfully.")
        except Exception as e:
            print(f"Error: Model loading failed - {e}")
            raise

    def predict(self, input_data: np.ndarray) -> np.ndarray:
        """
        Performs inference on the input data and returns the resulting probabilities.
        """
        with torch.no_grad():
            # 1. Convert numpy array to torch tensor
            # 2. Add batch dimension (1) and channel dimension (1) -> [1, 1, sequence_length]
            # 3. Send tensor to the correct device (cpu or cuda)
            input_tensor = torch.from_numpy(input_data).float().unsqueeze(0).unsqueeze(0)
            input_tensor = input_tensor.to(self.device)
            
            # Get raw model output (logits)
            output_logits = self.model(input_tensor)
            
            # Apply softmax to convert logits to probabilities
            probabilities = torch.nn.functional.softmax(output_logits, dim=1)
            
            # Move probabilities to CPU and convert back to a numpy array
            return probabilities.cpu().numpy()

