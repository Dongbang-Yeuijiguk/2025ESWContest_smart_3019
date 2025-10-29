# data_source/csv_reader.py

import pandas as pd
from typing import Iterator

class CSVReader:
    """
    Reads a large CSV file in chunks based on numerical time windows and strides.
    It returns chunks with a proper DatetimeIndex for convenient use.
    """
    def __init__(self, file_path: str, window_sec: float, step_sec: float, timestamp_col: str = 'real_timestamp'):
        """
        Initializes the reader, loads the CSV, and creates a separate
        datetime index for later use without affecting the numerical timestamp column.
        """
        print(f"Loading data from {file_path}...")
        try:
            self.df = pd.read_csv(file_path)
            
            # --- ✨ [CHANGE 1] ---
            # Create a new column for the DatetimeIndex.
            # The original numerical timestamp_col remains untouched for fast processing.
            self.df['datetime_index'] = pd.to_datetime(self.df[timestamp_col], unit='s')
            
            self.df.sort_values(by=timestamp_col, inplace=True)
            print("Data loaded and prepared successfully.")
        except Exception as e:
            print(f"Error loading or processing CSV file: {e}")
            raise
        
        self.timestamp_col = timestamp_col
        self.window_sec = window_sec
        self.step_sec = step_sec
        
        self.start_time = self.df[self.timestamp_col].min()
        self.end_time = self.df[self.timestamp_col].max()

    def __iter__(self) -> Iterator[pd.DataFrame]:
        """Returns the iterator object (self)."""
        return self

    def __next__(self) -> pd.DataFrame:
        """
        Yields the next chunk of data, setting the datetime column as
        the final index before returning.
        """
        current_window_end = self.start_time + self.window_sec
        
        if self.start_time >= self.end_time:
            raise StopIteration
        
        # Use fast numerical comparison on the original timestamp column
        mask = (self.df[self.timestamp_col] >= self.start_time) & \
               (self.df[self.timestamp_col] < current_window_end)
        chunk_df = self.df.loc[mask].copy() # Use .copy() to avoid SettingWithCopyWarning
        
        # --- ✨ [CHANGE 2] ---
        # Set the pre-made datetime column as the index on the final chunk
        # before returning it. This is what main_csv_test.py expects.
        chunk_df.set_index('datetime_index', inplace=True)
        
        # Move the start time for the next iteration
        self.start_time += self.step_sec
        
        return chunk_df