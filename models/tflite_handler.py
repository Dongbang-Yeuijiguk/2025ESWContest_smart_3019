# models/tflite_handler.py
import numpy as np
# Use the official TFLite Runtime for efficiency
import tflite_runtime.interpreter as tflite

class TFLiteModel:
    """
    Encapsulates TFLite model loading, tensor allocation, and inference.
    """
    
    def __init__(self, model_path: str):
        """
        Loads the TFLite model and initializes the interpreter.
        
        Args:
            model_path (str): The file path to the .tflite model.
        """
        print(f"Loading TFLite model from: {model_path}")
        try:
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            
            # Get input and output tensor details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            print("TFLite model loaded successfully.")
            print(f" - Input shape: {self.input_details[0]['shape']}")
            print(f" - Output shape: {self.output_details[0]['shape']}")

        except Exception as e:
            print(f"Error: TFLite model loading failed - {e}")
            raise

    def predict(self, input_data: np.ndarray) -> np.ndarray:
        """
        Performs inference on the input data and returns the resulting probabilities.
        
        Args:
            input_data (np.ndarray): A 1D numpy array of preprocessed signal data.
        
        Returns:
            np.ndarray: A 1D numpy array of class probabilities.
        """
        # 1. Reshape and cast the input data to match the model's requirements.
        # This safely converts a 1D array like (240,) into a 3D array like (1, 240, 1).
        reshaped_data = input_data.reshape(1, -1, 1).astype(np.float32)

        # 2. Set the value of the input tensor.
        self.interpreter.set_tensor(self.input_details[0]['index'], reshaped_data)
        
        # 3. Run the inference.
        self.interpreter.invoke()
        
        # 4. Get the raw output tensor (logits).
        logits = self.interpreter.get_tensor(self.output_details[0]['index'])
        
        # 5. Apply the Softmax function to convert logits to probabilities.
        # This step is crucial for consistency with the PyTorch handler.
        exp_logits = np.exp(logits - np.max(logits)) # Numerically stable softmax
        probabilities = exp_logits / np.sum(exp_logits)
        
        return probabilities