"""평가 환경 초기화 CLI 명령어"""

from importlib.resources import files
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml


def init(
    dir: Annotated[
        str,
        typer.Option("--dir", "-d", help="평가 산출물 디렉토리 (기본: .prompt-eval)"),
    ] = ".prompt-eval",
    targets_dir: Annotated[
        Optional[str],
        typer.Option("--targets-dir", "-t", help="프로덕션 프롬프트 위치"),
    ] = None,
    no_skills: Annotated[
        bool,
        typer.Option("--no-skills", help="Claude Code 스킬 설치 생략"),
    ] = False,
    no_eval_prompts: Annotated[
        bool,
        typer.Option("--no-eval-prompts", help="범용 평가 기준 복사 생략"),
    ] = False,
):
    """평가 환경 초기화 (targets 제외)."""
    eval_dir = Path(dir)

    # 1. 평가 산출물 디렉토리 생성
    for d in ["targets", "datasets", "eval_prompts", "results"]:
        (eval_dir / d).mkdir(parents=True, exist_ok=True)
    typer.echo(f"  {eval_dir}/ 디렉토리 생성 완료")

    # 2. config.yaml 생성
    _write_config(eval_dir, targets_dir)
    typer.echo(f"  {eval_dir}/config.yaml 생성 완료")

    # 3. 프로덕션 프롬프트 자동 감지
    if targets_dir:
        detected = _auto_detect_prompts(eval_dir, targets_dir)
        if detected:
            typer.echo(f"  프롬프트 {len(detected)}개 자동 감지:")
            for name in detected:
                typer.echo(f"    - {name}")
        else:
            typer.echo(f"  {targets_dir} 에서 프롬프트를 찾지 못했습니다.")

    # 4. Claude Code 스킬 복사
    if not no_skills:
        _copy_skills()
        typer.echo("  .claude/skills/ 스킬 설치 완료")

    # 5. 범용 평가 기준 복사
    if not no_eval_prompts:
        _copy_eval_prompts(eval_dir)
        typer.echo(f"  {eval_dir}/eval_prompts/general/ 범용 기준 복사 완료")

    # 6. GUIDE.md 복사
    _copy_guide(eval_dir)
    typer.echo(f"  {eval_dir}/GUIDE.md 사용 가이드 복사 완료")

    # 7. .gitignore 업데이트
    _update_gitignore(eval_dir)
    typer.echo("  .gitignore 업데이트 완료")

    typer.echo()
    typer.echo("평가 환경 초기화 완료!")
    if targets_dir:
        typer.echo(f"  프롬프트 경로: {targets_dir}")
    typer.echo(f"  평가 데이터: {eval_dir}/")
    typer.echo()
    typer.echo("다음 단계:")
    typer.echo(f"  0. {eval_dir}/GUIDE.md 에서 상세 사용법 확인")
    typer.echo("  1. Claude Code에서 /gen-testcases 로 테스트케이스 생성")
    typer.echo("  2. Claude Code에서 /eval-criteria 로 평가기준 생성")
    typer.echo("  3. prompt-eval experiment --name <프롬프트명> 으로 평가 실행")


def _auto_detect_prompts(eval_dir: Path, targets_dir: str) -> list[str]:
    """프로덕션 프롬프트 디렉토리에서 프롬프트 파일을 자동 감지하고 config.yaml 스켈레톤 생성.

    플랫 파일 구조를 가정: targets_dir/name.py, targets_dir/name.txt 등

    Returns:
        감지된 프롬프트 이름 목록
    """
    from prompt_evaluator.loaders.prompt_loader import SUPPORTED_EXTENSIONS

    src_dir = Path(targets_dir)
    if not src_dir.is_dir():
        return []

    detected = []
    for f in sorted(src_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        name = f.stem
        target_dir = eval_dir / "targets" / name
        config_file = target_dir / "config.yaml"

        if config_file.exists():
            continue  # 이미 설정됨

        # .py 파일이면 프롬프트 키 감지
        prompt_key = None
        if f.suffix.lower() == ".py":
            keys = _detect_prompt_keys(f)
            if not keys:
                continue  # *_PROMPT 변수가 없으면 프롬프트 파일이 아님
            if len(keys) == 1:
                prompt_key = keys[0]

        # config.yaml 스켈레톤 생성
        target_dir.mkdir(parents=True, exist_ok=True)
        config: dict = {
            "name": name,
            "prompt_file": str(f),
            "output_format": "text",
            "evaluators": [
                {"type": "rule_based", "checks": ["keyword_inclusion"]},
                {
                    "type": "llm_judge",
                    "enabled": True,
                    "criteria": ["general/instruction_following"],
                },
            ],
        }
        if prompt_key:
            config["prompt_key"] = prompt_key

        config_file.write_text(
            yaml.dump(
                config, default_flow_style=False, allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
        )
        detected.append(name)

    return detected


def _detect_prompt_keys(py_file: Path) -> list[str]:
    """Python 파일에서 *_PROMPT 변수명을 추출"""
    import ast

    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (
                    target.id.endswith("_PROMPT") or target.id == "PROMPT"
                ):
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, str
                    ):
                        keys.append(target.id)
    return keys


def _write_config(eval_dir: Path, targets_dir: str | None):
    """config.yaml 생성"""
    config: dict[str, str] = {"root": str(eval_dir)}
    if targets_dir:
        config["targets_dir"] = targets_dir

    config_path = eval_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _copy_skills():
    """패키지 번들 스킬을 .claude/skills/에 복사"""
    templates_skills = files("prompt_evaluator.skills")
    dest = Path(".claude") / "skills"

    for skill_dir in [
        "test_case_generator",
        "llm_judge_generator",
        "prompt_ab_comparator",
    ]:
        src = templates_skills.joinpath(skill_dir)
        dst = dest / skill_dir
        if dst.exists():
            continue  # 이미 있으면 덮어쓰지 않음
        _copy_resource_tree(src, dst)


def _copy_eval_prompts(eval_dir: Path):
    """범용 평가 기준을 eval_prompts/general/에 복사"""
    templates_prompts = files("prompt_evaluator.evaluators.eval_prompts.general")
    dest = eval_dir / "eval_prompts" / "general"
    dest.mkdir(parents=True, exist_ok=True)

    for item in templates_prompts.iterdir():
        if item.is_file() and item.name.endswith(".txt"):
            dst_file = dest / item.name
            if not dst_file.exists():
                dst_file.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_guide(eval_dir: Path):
    """번들 GUIDE.md를 평가 디렉토리에 복사"""
    guide_src = files("prompt_evaluator").joinpath("GUIDE.md")
    dst_file = eval_dir / "GUIDE.md"
    if not dst_file.exists():
        dst_file.write_text(guide_src.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_resource_tree(src, dst: Path):
    """importlib.resources traversable을 파일시스템에 복사"""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_file():
            target.write_bytes(item.read_bytes())
        elif item.is_dir():
            _copy_resource_tree(item, target)


def _update_gitignore(eval_dir: Path):
    """프로젝트 루트 .gitignore에 평가 results 경로 추가"""
    gitignore = Path(".gitignore")
    entry = f"{eval_dir}/results/"

    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content:
            return
    else:
        content = ""

    content += f"\n# prompt-eval results\n{entry}\n"
    gitignore.write_text(content)
