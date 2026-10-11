"""Money must reach Gemini already formatted, so the model can't mis-scale it."""
from backend.ai.money import humanize_money, rupees_text


def test_rupees_use_indian_grouping():
    assert rupees_text(11300000) == "Rs 1,13,000"
    assert rupees_text(5000000) == "Rs 50,000"
    assert rupees_text(62492000) == "Rs 6,24,920"
    assert rupees_text(180000) == "Rs 1,800"
    assert rupees_text(0) == "Rs 0"
    assert rupees_text(-1500000) == "-Rs 15,000"


def test_minor_fields_become_rupee_strings_everywhere():
    data = {"cost_minor": 11300000, "nested": [{"penalty_minor": 5000000, "qty": 80}], "flag_minor": True}
    out = humanize_money(data)
    assert out == {
        "cost_rupees": "Rs 1,13,000",
        "nested": [{"penalty_rupees": "Rs 50,000", "qty": 80}],
        "flag_minor": True,
    }
