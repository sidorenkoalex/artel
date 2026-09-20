"""Приёмочные тесты AC-5 и AC-10 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/
SPEC.md): таблица «модель -> минимальная версия CLI» в
`orchestrator/stack.py` и строки `check_stack()` по agent-ролям
`roles.yaml`, доезжающие до вывода `version`/`doctor`.

Красен до реализации: `orchestrator/stack.py` не несёт ни
`MODEL_MIN_CLI_VERSION` (обращение к атрибуту падает `AttributeError`),
ни строк «модель роли …» в `check_stack()` — искать в выводе нечего.

Две из трёх точек чтения таблицы проверяются соседними файлами планки:
предполётный отказ шага — `test_ac6_ac7_ac8_preflight_model_check.py`,
классификация провала попытки — `test_ac9_model_unsupported_class.py`.
Здесь — третья точка (`check_stack`) и сама таблица.

Печать строк командой `doctor` берётся не прогоном `doctor` целиком (он
зовёт живой смоук с реальным запуском агента — в приёмочном прогоне ему
не место), а сверкой двух фактов: `orchestrator/doctor/cli.py` вливает в
свой список проверок весь `stack.check_stack()` (строка
`checks.extend(doctor.stack.check_stack())`) и сам пакет doctor задачей
не меняется (`test_ac4_role_cmd_single_source.py`). Команда `version`
проверяется настоящим прогоном.
"""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (INCIDENT_MODEL, REPO_ROOT, UNKNOWN_MODEL,  # noqa: E402
                      claude_version_run, version_text)
from orchestrator import config, stack, version  # noqa: E402

ROLES_YAML = """roles:
  orchestrator:
    executor: system
    token_slot: artel-orchestrator
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model: {developer}
  reviewer:
    executor: agent
    token_slot: artel-reviewer
    skills: [conventions-core]
    model: {reviewer}
  verifier:
    executor: none
    token_slot: artel-verifier
    model: {verifier}
token_fallback: artel-token
"""


class StackModelCompatibilityTest(unittest.TestCase):
    """`check_stack()` настоящая: подменены только `roles.yaml`, таблица
    совместимости и ответ `claude --version`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.roles_path = Path(tmp.name) / "roles-under-test.yaml"
        self.set_roles(developer=INCIDENT_MODEL, reviewer=UNKNOWN_MODEL,
                       verifier=INCIDENT_MODEL)
        self.patch(config, "ROLES", self.roles_path)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_roles(self, developer, reviewer, verifier) -> None:
        self.roles_path.write_text(
            ROLES_YAML.format(developer=developer, reviewer=reviewer,
                              verifier=verifier), encoding="utf-8")

    def set_cli_version(self, text: str) -> None:
        self.patch(subprocess, "run", claude_version_run(text, subprocess.run))

    def set_table(self, table: dict) -> None:
        self.patch(stack, "MODEL_MIN_CLI_VERSION", dict(table))

    def model_checks(self, role: str) -> list:
        return [c for c in stack.check_stack()
                if "модель роли" in f"{c.name} {c.detail}"
                and role in f"{c.name} {c.detail}"]

    def single_model_check(self, role: str):
        checks = self.model_checks(role)
        self.assertEqual(len(checks), 1,
                         f"строк о модели роли {role}: {len(checks)} ({checks})")
        return checks[0]

    # --------------------------------------------------------------- AC-5

    def test_ac5_table_carries_the_incident_entry(self):
        """Таблица `MODEL_MIN_CLI_VERSION` лежит в `orchestrator/stack.py`
        и несёт запись инцидента 19.09.

        Ловит мутацию: таблица заведена не в `stack.py`, а рядом с
        потребителем (`runner.py`), либо запись инцидента записана с
        другой минимальной версией (`(2, 1, 0)`, строкой `"2.1.251"`).
        """
        self.assertEqual(stack.MODEL_MIN_CLI_VERSION[INCIDENT_MODEL],
                         (2, 1, 251))
        source = (REPO_ROOT / "orchestrator" / "stack.py").read_text(
            encoding="utf-8")
        self.assertIn("MODEL_MIN_CLI_VERSION", source)

    def test_ac5_code_reads_the_table_instead_of_repeating_the_numbers(self):
        """Минимальная версия берётся из таблицы: подменённая запись
        меняет и вердикт, и названное в строке число.

        Ловит мутацию: число `2.1.251` повторено по месту сравнения
        (`if version < (2, 1, 251)`), а таблица остаётся декорацией —
        подмена таблицы вердикт не меняет.
        """
        self.set_table({INCIDENT_MODEL: (7, 7, 7)})

        self.set_cli_version("7.7.6")
        low = self.single_model_check("developer")
        self.assertEqual(low.status, "fail", low.detail)
        self.assertIn("7.7.7", f"{low.name} {low.detail}")

        self.set_cli_version("7.7.8")
        high = self.single_model_check("developer")
        self.assertEqual(high.status, "ok", high.detail)

    def test_ac5_model_outside_the_table_is_not_a_refusal(self):
        """Пустая таблица не отказывает никому: модель, которой в ней
        нет, — не провал даже при древнем CLI.

        Ловит мутацию: отсутствие модели в таблице трактуется как
        «несовместима» (fail-closed) — любая новая модель Оператора
        валит `doctor`/шаг до правки таблицы.
        """
        self.set_table({})
        self.set_cli_version("1.0.0")

        statuses = [c.status for c in stack.check_stack()
                    if "модель роли" in f"{c.name} {c.detail}"]

        self.assertTrue(statuses, "строки о моделях ролей не найдены вовсе")
        self.assertNotIn("fail", statuses)

    # -------------------------------------------------------------- AC-10

    def test_ac10_one_line_per_agent_role_with_a_model(self):
        """По строке на agent-роль с полем `model`: `ok` для модели,
        которую CLI тянет, `warn` для модели вне таблицы; роль без
        `executor: agent` строки не получает даже с полем `model`.

        Ловит мутацию: строка печатается на каждую роль `roles.yaml`
        подряд (включая `verifier`/`orchestrator`), либо модель вне
        таблицы даёт `ok`/`fail` вместо `warn`.
        """
        self.set_table({INCIDENT_MODEL: (2, 1, 251)})
        self.set_cli_version("2.1.267")

        ok = self.single_model_check("developer")
        self.assertEqual(ok.status, "ok", ok.detail)
        text = f"{ok.name} {ok.detail}"
        for fragment in (INCIDENT_MODEL, "2.1.267", "2.1.251", "≥"):
            self.assertIn(fragment, text)

        unknown = self.single_model_check("reviewer")
        self.assertEqual(unknown.status, "warn", unknown.detail)
        self.assertIn(UNKNOWN_MODEL, f"{unknown.name} {unknown.detail}")

        self.assertEqual(self.model_checks("verifier"), [],
                         "verifier — не agent-роль, строки о модели не ждём")
        self.assertEqual(self.model_checks("orchestrator"), [],
                         "orchestrator — не agent-роль, строки о модели не ждём")

    def test_ac10_line_fails_when_the_installed_cli_is_below_the_minimum(self):
        """Заниженная версия CLI для модели роли — `fail` строки стека, а
        не предупреждение.

        Ловит мутацию: заниженная версия отмечается `warn` (как
        `_tool_check` отмечает свой минимум инструмента) — `doctor`
        остаётся зелёным при заведомо нерабочей модели роли.
        """
        minimum = stack.MODEL_MIN_CLI_VERSION[INCIDENT_MODEL]
        below = (minimum[0], minimum[1], minimum[2] - 1)
        self.set_cli_version(version_text(below))

        check = self.single_model_check("developer")

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(version_text(minimum), f"{check.name} {check.detail}")

    def test_ac10_lines_reach_the_version_and_doctor_output(self):
        """Строки печатаются командой `version` и вливаются в список
        проверок `doctor` — без правки `orchestrator/version.py` и
        `orchestrator/doctor/`.

        Ловит мутацию: строки заведены отдельной функцией стека, которую
        никто не зовёт (`check_stack()` их не возвращает) — вывод
        `version`/`doctor` о моделях ролей молчит.
        """
        self.set_table({INCIDENT_MODEL: (2, 1, 251)})
        self.set_cli_version("2.1.267")

        buf = io.StringIO()
        with redirect_stdout(buf):
            version.cmd_version()
        out = buf.getvalue()

        self.assertIn("модель роли", out)
        self.assertIn(INCIDENT_MODEL, out)
        doctor_cli = (REPO_ROOT / "orchestrator" / "doctor" / "cli.py").read_text(
            encoding="utf-8")
        self.assertIn("stack.check_stack()", doctor_cli)


if __name__ == "__main__":
    unittest.main()
