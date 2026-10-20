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


def test_install_resolve_puts_a_launcher_in_the_scripts_menu(tmp_path):
    from fusion2lottie import resolve

    launcher = resolve.install(scripts=tmp_path / "Scripts/Utility", library=tmp_path / "lib")
    assert launcher.name == "Export to Lottie.py"
    assert (tmp_path / "lib/fusion2lottie/convert.py").exists()
    text = launcher.read_text()
    assert repr(str(tmp_path / "lib")) in text and "menu(resolve, fusion)" in text
    compile(text, str(launcher), "exec")
    assert sorted(p.name for p in resolve.uninstall(scripts=tmp_path / "Scripts/Utility", library=tmp_path / "lib")) \
        == ["Export to Lottie.py", "fusion2lottie"]


def test_samples_file_feeds_inputs_only_fusion_can_evaluate(tmp_path, capsys):
    from test_convert import SPIN, comp_with

    comp = tmp_path / "spin.comp"
    comp.write_text(comp_with(SPIN))
    assert main([str(comp), "--check"]) == 1
    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps({"Spin.ZRotation": [0] * 10, "Spin.Center": [[0, 0]] * 10}))
    assert main([str(comp), "--samples", str(samples), "--fps", "24"]) == 0
    assert json.loads((tmp_path / "spin.json").read_text())["fr"] == 24
