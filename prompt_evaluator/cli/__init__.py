"""CLI 모듈 - prompt-eval 엔트리 포인트"""

import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(name="prompt-evaluator", help="프롬프트 평가 시스템 CLI")


def _register():
    from prompt_evaluator.cli import prompt as prompt_cli, baseline as baseline_cli
    from prompt_evaluator.cli.experiment import experiment, regression
    from prompt_evaluator.cli.config import validate
    from prompt_evaluator.cli.dataset import list_sets, upload
    from prompt_evaluator.cli.scaffold import init

    app.add_typer(prompt_cli.app, name="prompt")
    app.add_typer(baseline_cli.app, name="baseline")
    app.command()(init)
    app.command()(experiment)
    app.command()(regression)
    app.command()(validate)
    app.command(name="list")(list_sets)
    app.command()(upload)


_register()
