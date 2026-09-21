"""Тонкая надстройка сценария «каталог моделей и ярус роли» над песочницами
`tests/`.

Своих копий песочниц здесь нет (skills/test-authoring.md, роадмап §4):
шаг роли берётся готовым из `tests/test_runner_model_preflight.py`
(`_StepSandbox` — настоящий путь `runner.cmd_run`/`auto.cmd_auto` с
подменённым процессом агента), окружение `doctor` — из
`tests/test_doctor.py` (`_DoctorTmpRootTest`), временный корень пульта —
`tests/sandbox.py::TmpRootTest`. Здесь — только то, чего в них нет:
каталог моделей и локальный слой во временном корне, карта исполнителей
с `model_tier:` и набор подмен, под которыми `doctor` не зовёт живой CLI.

`orchestrator.models` этот модуль НЕ импортирует на верхнем уровне (см.
`_models.module()`): сухой сбор планки на выходе `tests_writing`
импортирует и вспомогательные модули тоже.
"""
import contextlib
from unittest import mock

import _models
from orchestrator import config, doctor, runner
from tests.sandbox import TmpRootTest, claude_only_popen, claude_only_run
from tests.test_doctor import FakeLiveSmokeProc  # noqa: F401
from tests.test_doctor import TmpRootTest as _DoctorTmpRootTest
from tests.test_doctor import result_event
from tests.test_runner_model_preflight import _StepSandbox

# Ярус вне закрытого перечня `strong | standard | cheap` (AC-6, AC-7).
FOREIGN_TIER = "yarus-kotorogo-net-v-perechne"


class _ModelsFixturesMixin:
    """Каталог моделей, локальный слой и карта исполнителей с ярусами во
    временном корне песочницы."""

    ROLE = "developer"

    def seed_model_paths(self) -> None:
        """Пути каталога и локального слоя — во временный корень.

        `TmpRootTest` подменяет фиксированный список путей `config`, новой
        константы пути каталога в нём нет (см. `_models.path_patchers`)."""
        for patcher in _models.path_patchers(self.root):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.catalog_path = self.root / _models.CATALOG_NAME
        self.local_path = self.root / _models.LOCAL_DIR / _models.CATALOG_NAME
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

    def write_catalog(self, text: str | None = None) -> None:
        """Каталог во временном корне: по умолчанию — дословный
        `models.yaml` рабочей копии (форму записи планка не сочиняет)."""
        self.catalog_path.write_text(
            _models.catalog_text() if text is None else text, encoding="utf-8")

    def write_local(self, text: str) -> None:
        self.local_path.write_text(text, encoding="utf-8")

    def default_tiers(self, model: str = _models.OPUS) -> dict:
        return {tier: model for tier in _models.TIERS}

    def set_roles_tiers(self, tier_by_role: dict) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(_models.roles_yaml_with_tiers(tier_by_role),
                        encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)


class CatalogSandbox(_ModelsFixturesMixin, TmpRootTest):
    """Временный корень пульта с каталогом моделей и локальным слоем."""

    def setUp(self):
        super().setUp()
        self.seed_model_paths()


class TierStepSandbox(_ModelsFixturesMixin, _StepSandbox):
    """Шаг роли `developer` с управляемым ярусом роли и каталогом моделей.

    `_StepSandbox` (tests/) остаётся единственным источником самого шага:
    отвязка `runner.cmd_run`/`auto.cmd_auto` от настоящего процесса
    агента, журнал, `self.exit_message` отказа."""

    def setUp(self):
        super().setUp()
        self.seed_model_paths()

    def seed_chain(self, tier: str | None = "strong",
                   catalog_text: str | None = None,
                   local_text: str | None = None) -> None:
        """Полная разрешимая цепочка: каталог, локальный слой, ярус роли.
        `tier=None` — роль без `model_tier` вовсе (AC-7)."""
        self.write_catalog(catalog_text)
        self.write_local(local_text if local_text is not None
                         else _models.local_texts(self.default_tiers())[0])
        self.set_roles_tiers({self.ROLE: tier})

    def refusal_text(self, printed: str) -> str:
        """Всё, что шаг сказал Оператору: stdout плюс текст `sys.exit` —
        отказ до старта агента оформлен то одним, то другим (`return`
        против `sys.exit`), а критерий говорит про строку отказа."""
        return f"{printed}\n{self.exit_message or ''}"


class ModelsDoctorSandbox(_ModelsFixturesMixin, _DoctorTmpRootTest):
    """Окружение `doctor` (tests/test_doctor.py) с каталогом моделей."""

    def setUp(self):
        super().setUp()
        self.seed_model_paths()


def doctor_patchers(popen=None) -> list:
    """Подмены, под которыми `doctor` остаётся офлайн: живой смоук не зовёт
    настоящий CLI, `claude --version` отвечает пином, keychain отдаёт
    токен. Тот же набор, что `tests/test_doctor.py` применяет к
    `all_checks`."""
    proc = FakeLiveSmokeProc(result_event(0.01))
    return [
        mock.patch.object(doctor.subprocess, "Popen",
                          popen if popen is not None
                          else claude_only_popen(proc)),
        mock.patch.object(doctor.subprocess, "run", claude_only_run(
            f"{config.CLI_VERSION_PIN} (Claude Code)\n")),
        mock.patch.object(runner.keychain, "token", lambda slot: "tok-test"),
    ]


@contextlib.contextmanager
def offline_doctor(popen=None):
    """Контекст всех подмен `doctor_patchers` разом."""
    with contextlib.ExitStack() as stack:
        for patcher in doctor_patchers(popen):
            stack.enter_context(patcher)
        yield


def rendered_checks(checks) -> str:
    """Проверки строками ровно так, как их печатает `cmd_doctor`
    (`orchestrator/doctor/cli.py`) — вывод команды без её побочных
    эффектов."""
    return "\n".join(f"  [{doctor.LABELS[c.status]}] {c.name}: {c.detail}"
                     for c in checks)
