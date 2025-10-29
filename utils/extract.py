# Functions for extracting amplitude and phase from CSI data

import numpy as np
import pandas as pd
import ast

def amp_phase_from_csi(data, column='data'):
    """
    Extracts amplitude and phase from CSI data string.

    Args:
        data (pd.DataFrame or pd.Series): The input data.
        column (str): The column name containing the CSI string if data is a DataFrame.

    Returns:
        tuple: A tuple containing Amp (N, 52) and Pha (N, 52) numpy arrays.
    """
    # --- Ensure we have a Series ---
    if isinstance(data, pd.DataFrame):
        s = data[column]
    else:
        s = data  # Already a Series

    N = len(s)
    AmpCSI = np.zeros((N, 64), dtype=np.float64)
    PhaseCSI = np.zeros((N, 64), dtype=np.float64)

    for i in range(N):
        item = s.iat[i]  # Use integer-location based indexing
        if pd.isna(item):
            # If data is missing, leave as zeros and continue
            continue

        # Safely parse the string into a list
        if isinstance(item, str):
            try:
                values = ast.literal_eval(item.strip())
            except (ValueError, SyntaxError):
                # If parsing fails, skip this row
                continue
        else:
            # If it's already a list/array, convert to list
            values = list(item)

        # Ensure the sequence of real/imaginary parts has the correct length
        if len(values) < 2 * 64:
            # For now, we will raise an error if the data is too short.
            # A padding policy could be implemented here if needed.
            # e.g., values = (values + [0]*(2*64 - len(values)))[:2*64]
            # print(f"Warning: [row {i}] Data has fewer than 128 values: len={len(values)}. Skipping.")
            continue
        values = values[:2 * 64]

        # Even indices = Imaginary, Odd indices = Real
        ImCSI = np.asarray(values[::2], dtype=np.int64)   # Shape: (64,)
        ReCSI = np.asarray(values[1::2], dtype=np.int64)  # Shape: (64,)

        # Calculate Amplitude and Phase
        AmpCSI[i, :] = np.hypot(ImCSI, ReCSI)      # = sqrt(Im^2 + Re^2)
        PhaseCSI[i, :] = np.arctan2(ImCSI, ReCSI)  # arctan2(y=Im, x=Re)

    # Select subcarriers: 0-based indices 6..31 and 33..58
    # This corresponds to slices 6:32 and 33:59
    Amp = np.concatenate([AmpCSI[:, 6:32], AmpCSI[:, 33:59]], axis=1)  # Shape: (N, 52)
    Pha = np.concatenate([PhaseCSI[:, 6:32], PhaseCSI[:, 33:59]], axis=1)  # Shape: (N, 52)
    return Amp, Pha
