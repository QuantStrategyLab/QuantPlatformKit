from __future__ import annotations

import unittest

import pandas as pd

from quant_platform_kit.common.history import normalize_history_frame


class CommonHistoryTests(unittest.TestCase):
    def test_normalize_history_frame_accepts_dataframe_with_close_column(self) -> None:
        frame = pd.DataFrame([{"close": 1.0}, {"close": 2.0}])

        normalized = normalize_history_frame(frame, label="benchmark_history")

        self.assertEqual(list(normalized["close"]), [1.0, 2.0])

    def test_normalize_history_frame_accepts_dataframe_with_close_case_variant(self) -> None:
        frame = pd.DataFrame([{"Close": 1.0}, {"Close": 2.0}])

        normalized = normalize_history_frame(frame, label="benchmark_history")

        self.assertEqual(list(normalized["close"]), [1.0, 2.0])

    def test_normalize_history_frame_accepts_series(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0], name="close")

        normalized = normalize_history_frame(series, label="benchmark_history")

        self.assertEqual(list(normalized["close"]), [1.0, 2.0, 3.0])

    def test_normalize_history_frame_accepts_single_column_iterable(self) -> None:
        history = [1.0, 2.0, 3.0]

        normalized = normalize_history_frame(history, label="benchmark_history")

        self.assertEqual(list(normalized["close"]), [1.0, 2.0, 3.0])

    def test_normalize_history_frame_rejects_missing_close_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "benchmark_history must include a close column"):
            normalize_history_frame([{"open": 1.0, "high": 1.0}], label="benchmark_history")


if __name__ == "__main__":
    unittest.main()
