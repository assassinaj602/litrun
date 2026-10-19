from click.testing import CliRunner
from litrun.cli.main import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "litrun" in result.output


def test_cli_inspect():
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect"])
    assert result.exit_code == 0
    assert "System & Processor" in result.output
    assert "Memory Envelope" in result.output


def test_cli_inspect_json():
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--json"])
    assert result.exit_code == 0
    assert "profile_id" in result.output
    assert "hardware" in result.output


def test_cli_list():
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "qwen2.5-0.5b" in result.output


def test_cli_run_prompt():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "qwen2.5-0.5b", "--prompt", "Hello", "--demo"])
    assert result.exit_code == 0
    assert "Detected:" in result.output
    assert "Selected:" in result.output
    assert "Warmup complete" in result.output


def test_cli_benchmark():
    runner = CliRunner()
    result = runner.invoke(cli, ["benchmark", "qwen2.5-0.5b", "-n", "16"])
    assert result.exit_code == 0
    assert "Inference Benchmark Results" in result.output
    assert "Tokens / Sec" in result.output
