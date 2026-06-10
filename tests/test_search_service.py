from datetime import date

import pytest

from mirrorquant_demo.search_service import validate_hero_window

def test_validate_hero_window_rejects_start_date_after_end_date():
    with pytest.raises(ValueError) as exc_info:
        validate_hero_window(
            ticker="MSFT",
            start_date=date(2024, 3, 10), 
            end_date=date(2024, 1, 10),
        )
    assert "start_date must be on or before end_date" in str(exc_info.value)