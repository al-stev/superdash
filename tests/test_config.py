from superpowers_dashboard.config import load_config, DEFAULT_PRICING


def test_default_pricing_has_opus():
    assert "claude-opus-4-6" in DEFAULT_PRICING
    pricing = DEFAULT_PRICING["claude-opus-4-6"]
    assert pricing["input"] == 5.0
    assert pricing["output"] == 25.0
    assert pricing["cache_read"] == 0.5
    assert pricing["cache_write"] == 6.25


def test_load_config_returns_defaults_when_no_file(tmp_path):
    config = load_config(config_path=tmp_path / "nonexistent.toml")
    assert config["pricing"] == DEFAULT_PRICING


def test_load_config_reads_toml_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[pricing."claude-opus-4-6"]
input = 10.0
output = 50.0
cache_read = 1.0
cache_write = 12.5
''')
    config = load_config(config_path=config_file)
    assert config["pricing"]["claude-opus-4-6"]["input"] == 10.0


def test_load_config_merges_with_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[pricing."claude-opus-4-6"]
input = 10.0
output = 50.0
cache_read = 1.0
cache_write = 12.5
''')
    config = load_config(config_path=config_file)
    assert config["pricing"]["claude-opus-4-6"]["input"] == 10.0
    assert "claude-sonnet-4-5-20250929" in config["pricing"]
