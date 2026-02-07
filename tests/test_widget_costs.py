from superpowers_dashboard.widgets.costs_panel import CostsWidget, format_cache_ratio

def test_format_cache_ratio():
    assert format_cache_ratio(680, 1000) == "68%"

def test_format_cache_ratio_zero():
    assert format_cache_ratio(0, 0) == "0%"

def test_costs_widget_format_summary():
    w = CostsWidget()
    text = w.format_summary(total_cost=0.42, input_tokens=12847, output_tokens=3291, cache_read_tokens=8700)
    assert "$0.42" in text
    assert "12,847" in text
    assert "3,291" in text
