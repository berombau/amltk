"""Measure things about data."""
from __future__ import annotations

import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


def byte_size(data: Any | Iterable[Any]) -> int:
    """Measure the size of data.

    Works for numpy-arrays, pandas DataFrames and Series, and iterables of any of
    these.

    Args:
        data: The data to measure.

    Returns:
        The size of the data.
    """
    if isinstance(data, np.ndarray):
        return data.nbytes
    if isinstance(data, pd.DataFrame):
        return data.memory_usage(deep=True).sum()
    if isinstance(data, pd.Series):
        return data.memory_usage(deep=True)
    if isinstance(data, Iterable):
        return sum(byte_size(d) for d in data)

    return sys.getsizeof(data)
