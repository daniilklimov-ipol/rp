import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from ytpredictor import paths


@pytest.fixture
def isolated_appdata(tmp_path, monkeypatch):
    """Point all app-data paths (db, model, config) at a throwaway tmp dir."""
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path)
    return tmp_path
