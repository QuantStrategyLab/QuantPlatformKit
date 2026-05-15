from __future__ import annotations

import pandas as pd


def normalize_history_frame(history, *, label: str, close_column: str = "close") -> pd.DataFrame:
    if isinstance(history, pd.DataFrame):
        frame = history.copy()
    elif isinstance(history, pd.Series):
        frame = history.to_frame(name=close_column)
    else:
        frame = pd.DataFrame(list(history))

    if frame.empty:
        raise ValueError(f"{label} must contain close history")

    normalized_close = str(close_column or "close").strip() or "close"
    lower_columns = {str(column).strip().lower(): column for column in frame.columns}
    if normalized_close not in frame.columns:
        close_match = lower_columns.get(normalized_close.lower())
        if close_match is not None:
            frame = frame.rename(columns={close_match: normalized_close})
        elif len(frame.columns) == 1:
            frame = frame.rename(columns={frame.columns[0]: normalized_close})
        else:
            columns = ", ".join(str(column) for column in frame.columns)
            raise ValueError(f"{label} must include a {normalized_close} column; got columns: {columns or '<none>'}")

    frame[normalized_close] = pd.to_numeric(frame[normalized_close], errors="coerce")
    frame = frame.dropna(subset=[normalized_close]).reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"{label} close history is empty after normalization")
    return frame
