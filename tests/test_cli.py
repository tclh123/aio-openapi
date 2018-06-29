from unittest.mock import patch
from click.testing import CliRunner

from openapi.rest import rest


def test_usage():
    runner = CliRunner()
    result = runner.invoke(rest())
    assert result.exit_code == 0
    assert result.output.startswith('Usage:')


def test_version():
    runner = CliRunner()
    result = runner.invoke(rest(), ['--version'])
    assert result.exit_code == 0
    assert result.output.startswith('Open API')


def test_serve():
    runner = CliRunner()
    cli = rest(base_path='/v1')
    with patch('aiohttp.web.run_app') as mock:
        result = runner.invoke(cli, ['serve'])
        assert result.exit_code == 0
        assert mock.call_count == 1
        app = mock.call_args[0][0]
        assert app.router
