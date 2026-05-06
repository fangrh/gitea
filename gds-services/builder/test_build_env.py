import importlib.util
import pathlib
import subprocess

_MAIN_PATH = pathlib.Path(__file__).with_name("main.py")
_SPEC = importlib.util.spec_from_file_location("gds_builder_main", _MAIN_PATH)
assert _SPEC and _SPEC.loader
main = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(main)


def test_run_build_enables_instance_provenance(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    snakefile = tmp_path / "Snakefile"
    snakefile.write_text("rule all:\n    input: []\n", encoding="utf-8")

    main._run_build("designs/example_mzi.py", pathlib.Path(tmp_path))

    env = captured["kwargs"]["env"]
    assert env["GDS_PROJECT_ROOT"] == str(tmp_path)
    assert env["GDS_PROVENANCE"] == "1"
