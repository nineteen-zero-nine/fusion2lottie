import json
import shutil
from pathlib import Path

from fusion2lottie.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_converts_next_to_the_comp_by_default(tmp_path, capsys):
    comp = tmp_path / "intro.comp"
    shutil.copy(FIXTURES / "valhalla-intro.comp", comp)
    assert main([str(comp), "--fps", "30"]) == 0
    lottie = json.loads((tmp_path / "intro.json").read_text())
    assert lottie["op"] == 90
    assert "wrote" in capsys.readouterr().out


def test_warns_when_the_frame_rate_is_assumed(tmp_path, capsys):
    assert main([str(FIXTURES / "valhalla-intro.comp"), "-o", str(tmp_path / "x.json")]) == 0
    assert "no --fps given: assumed 30" in capsys.readouterr().err


def test_check_writes_nothing(tmp_path, capsys):
    comp = tmp_path / "intro.comp"
    shutil.copy(FIXTURES / "valhalla-intro.comp", comp)
    assert main([str(comp), "--check"]) == 0
    assert capsys.readouterr().out.strip() == "converts cleanly"
    assert not (tmp_path / "intro.json").exists()


def test_unreadable_comp_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.comp"
    bad.write_text("Composition { Tools = {")
    assert main([str(bad)]) == 2
    assert "cannot read" in capsys.readouterr().err
