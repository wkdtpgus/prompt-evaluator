"""파이프라인 러너

사용자 파이프라인 함수를 동적으로 임포트하고 실행합니다.
config.yaml의 pipeline 설정에 따라 동작합니다.
"""

import asyncio
import importlib
import json
import os
import sys
from typing import Any


class PipelineRunner:
    """사용자 파이프라인을 동적으로 로드하고 실행하는 러너.

    Args:
        pipeline_config: config.yaml의 pipeline 섹션 dict
    """

    def __init__(self, pipeline_config: dict):
        self.config = pipeline_config
        self._callable = None
        self._input_model_class = None
        self._setup()

    def _setup(self):
        """파이프라인 callable과 input_model을 로드."""
        self._ensure_sys_path()
        self._callable = self._load_callable()
        if self.config.get("input_model"):
            self._input_model_class = self._import_object(self.config["input_model"])

    def _ensure_sys_path(self):
        """CWD를 sys.path에 추가하여 사용자 모듈을 import 가능하게 함."""
        cwd = os.getcwd()
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

    def _import_object(self, dotted_path: str) -> Any:
        """dotted path에서 모듈과 객체를 분리하여 임포트.

        예: 'src.services.workflow.PrepOutputPipeline'
          -> import src.services.workflow, getattr('PrepOutputPipeline')
        """
        parts = dotted_path.rsplit(".", 1)
        if len(parts) == 1:
            return importlib.import_module(parts[0])

        module_path, attr_name = parts
        try:
            module = importlib.import_module(module_path)
            return getattr(module, attr_name)
        except ImportError:
            raise ImportError(
                f"모듈을 찾을 수 없음: {module_path}\n"
                f"프로젝트 루트에서 실행하고 있는지 확인하세요.\n"
                f"sys.path: {sys.path[:3]}..."
            )
        except AttributeError:
            raise AttributeError(
                f"'{attr_name}'을(를) 모듈 '{module_path}'에서 찾을 수 없음"
            )

    def _resolve_init_args(self, init_args: dict) -> dict:
        """init_args 내 ${ENV_VAR} 참조를 환경변수 값으로 치환."""
        resolved = {}
        for key, value in init_args.items():
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_key = value[2:-1]
                resolved[key] = os.environ.get(env_key, "")
            else:
                resolved[key] = value
        return resolved

    def _load_callable(self):
        """config에 따라 callable을 구성.

        Returns:
            호출 가능한 바인드된 메서드
        """
        module = importlib.import_module(self.config["module"])

        class_name = self.config.get("class")
        if not class_name:
            raise ValueError(
                "pipeline.class는 필수입니다. 호출할 클래스 이름을 지정하세요."
            )

        try:
            cls = getattr(module, class_name)
        except AttributeError:
            raise AttributeError(
                f"클래스 '{class_name}'을(를) 모듈 '{self.config['module']}'에서 찾을 수 없음"
            )

        # 클래스 인스턴스화
        init_args = self.config.get("init_args", {})
        if init_args:
            init_args = self._resolve_init_args(init_args)
        instance = cls(**init_args)

        # 메서드 바인딩
        method_name = self.config.get("method")
        if method_name:
            try:
                return getattr(instance, method_name)
            except AttributeError:
                raise AttributeError(
                    f"메서드 '{method_name}'을(를) '{class_name}'에서 찾을 수 없음"
                )

        # method 미지정 시 __call__ 사용
        if callable(instance):
            return instance

        raise ValueError(f"{class_name}에 method를 지정하거나 __call__을 구현하세요.")

    def convert_input(self, inputs: dict) -> Any:
        """test_cases의 inputs dict를 파이프라인 입력으로 변환.

        input_model이 지정된 경우 Pydantic 모델 인스턴스로 변환.
        미지정 시 dict 그대로 반환.
        """
        if self._input_model_class is None:
            return inputs

        try:
            return self._input_model_class(**inputs)
        except Exception as e:
            raise ValueError(
                f"입력 변환 실패 ({self.config['input_model']}): {e}\n"
                f"입력 키: {list(inputs.keys())}"
            ) from e

    def normalize_output(self, raw_output: Any) -> str:
        """파이프라인 반환값을 평가용 문자열로 변환.

        output_key가 지정된 경우 해당 필드를 추출한 후 변환.
        """
        output = raw_output

        # output_key로 필드 추출
        output_key = self.config.get("output_key")
        if output_key:
            if isinstance(output, dict):
                output = output.get(output_key, output)
            elif hasattr(output, output_key):
                output = getattr(output, output_key)
            elif hasattr(output, "model_dump"):
                output = output.model_dump().get(output_key, output)

        # 문자열 변환
        if isinstance(output, str):
            return output
        if isinstance(output, (dict, list)):
            return json.dumps(output, ensure_ascii=False, indent=2)
        if hasattr(output, "model_dump"):
            return json.dumps(output.model_dump(), ensure_ascii=False, indent=2)

        return str(output)

    def run(self, inputs: dict) -> str:
        """파이프라인 실행: 입력 변환 -> 호출 -> 출력 정규화.

        Args:
            inputs: test_cases의 inputs dict

        Returns:
            평가용 문자열 출력
        """
        try:
            converted_input = self.convert_input(inputs)
        except Exception as e:
            raise ValueError(f"파이프라인 입력 변환 실패: {e}") from e

        try:
            if self._input_model_class is not None:
                raw_output = self._callable(converted_input)
            else:
                try:
                    raw_output = self._callable(**converted_input)
                except TypeError:
                    raw_output = self._callable(converted_input)
        except Exception as e:
            raise RuntimeError(
                f"파이프라인 실행 실패 ({self.config['module']}.{self.config.get('class', '')}"
                f".{self.config.get('method', '__call__')}): {e}"
            ) from e

        # async 메서드 지원: 코루틴이면 실행
        import inspect

        if inspect.isawaitable(raw_output):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # 이미 이벤트 루프 안 (Langfuse 등) → 새 스레드에서 독립 루프 생성
                import concurrent.futures

                def _run_coro(coro):
                    new_loop = asyncio.new_event_loop()
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    raw_output = pool.submit(_run_coro, raw_output).result()
            else:
                raw_output = asyncio.run(raw_output)

        return self.normalize_output(raw_output)


def is_pipeline_mode(eval_config: dict) -> bool:
    """config에 pipeline 설정이 있는지 확인."""
    return "pipeline" in eval_config and isinstance(eval_config["pipeline"], dict)


def create_pipeline_runner(eval_config: dict) -> PipelineRunner:
    """config에서 PipelineRunner를 생성.

    Args:
        eval_config: config.yaml 전체 dict

    Returns:
        PipelineRunner 인스턴스

    Raises:
        ValueError: pipeline config가 유효하지 않은 경우
    """
    pipeline_config = eval_config.get("pipeline", {})
    if not pipeline_config.get("module"):
        raise ValueError("pipeline.module은 필수입니다.")
    if not pipeline_config.get("class"):
        raise ValueError("pipeline.class는 필수입니다.")
    return PipelineRunner(pipeline_config)
