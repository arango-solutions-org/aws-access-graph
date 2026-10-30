import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_results_page_matches_expected_results():
    spec = importlib.util.spec_from_file_location("render_results", ROOT / "tools" / "render_results.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (ROOT / "docs" / "RESULTS.md").read_text() == mod.render(), \
        "docs/RESULTS.md is stale: run python tools/render_results.py"
