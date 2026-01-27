"""프롬프트 평가 CLI

Usage:
    # 설정 검증
    poetry run python main.py validate --name prep_generate
    poetry run python main.py validate --all

    # LangSmith Experiment (정식 평가)
    poetry run python main.py experiment --name prep_generate

    # 프롬프트 버전 관리
    poetry run python main.py prompt push --name prep_generate --tag v1.0
    poetry run python main.py prompt versions --name prep_generate

    # 기준선 및 회귀 테스트
    poetry run python main.py baseline list prep_generate
    poetry run python main.py regression --name prep_generate --experiment "..."

    # 평가 세트 목록
    poetry run python main.py list

    # 사용 가능한 평가 기준 확인
    poetry run python main.py criteria
"""

import typer
from dotenv import load_dotenv

# CLI 모듈 import
from cli import prompt as prompt_cli
from cli import baseline as baseline_cli
from cli.experiment import experiment, regression
from cli.config import validate, criteria
from cli.dataset import list_sets, upload

load_dotenv()

app = typer.Typer(
    name="prompt-evaluator",
    help="프롬프트 평가 시스템 CLI"
)

# 서브커맨드 등록
app.add_typer(prompt_cli.app, name="prompt")
app.add_typer(baseline_cli.app, name="baseline")

# 개별 명령어 등록
app.command()(experiment)
app.command()(regression)
app.command()(validate)
app.command()(criteria)
app.command(name="list")(list_sets)
app.command()(upload)


if __name__ == "__main__":
    app()
