from __future__ import annotations

import pandas as pd

from src.quant.data.storage import read_parquet, table_path, write_parquet


def test_parquet_round_trip(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "symbol": ["600001", "000002"],
            "close": [10.5, 12.25],
            "is_suspended": [False, True],
        }
    )

    output = write_parquet(df, "daily_bar", root=tmp_path)
    loaded = read_parquet("daily_bar", root=tmp_path)

    assert output == tmp_path / "daily_bar" / "data.parquet"
    assert table_path("daily_bar", root=tmp_path) == tmp_path / "daily_bar"
    pd.testing.assert_frame_equal(loaded, df)
