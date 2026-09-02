from __future__ import annotations

from importlib.metadata import metadata

import pytest

from supadl import __version__
from supadl.cli.main import build_parser, main


def test_package_version_matches_m0_version() -> None:
    assert __version__ == "0.1.0.dev0"


def test_installed_metadata_matches_runtime_version() -> None:
    package_metadata = metadata("supadl")

    assert package_metadata["Version"] == __version__
    assert set(package_metadata["Requires-Python"].split(",")) == {">=3.14", "<3.15"}


def test_no_argument_entrypoint_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "SupaDL download manager" in output
    assert "--version" in output


def test_version_argument_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(["--version"])

    assert error.value.code == 0
    assert capsys.readouterr().out.strip() == f"supadl {__version__}"
