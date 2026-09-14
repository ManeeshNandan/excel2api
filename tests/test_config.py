from excel2api.config import load_sync_config


def test_load_sync_config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("""\ninput: data.xlsx\nschema: schema.yaml\napi:\n  base_url: https://example.test\n  timeout: 10\nsync:\n  batch_size: 25\n""")
    config = load_sync_config(path)
    assert config["api"]["base_url"] == "https://example.test"
    assert config["sync"]["batch_size"] == 25
