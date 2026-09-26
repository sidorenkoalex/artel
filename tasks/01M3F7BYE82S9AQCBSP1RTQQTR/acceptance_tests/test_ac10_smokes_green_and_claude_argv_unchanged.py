"""AC-10 — 01M3F7BYE82S9AQCBSP1RTQQTR: смоки изоляции обоих провайдеров
зелены, argv шага роли на Claude не изменилось относительно main.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Проверки codex-isolation-smoke и isolation-smoke Claude остаются
зелёными, а argv команды шага роли на Claude совпадает с argv на main
(f89bab7c) — зафиксировано тестом.

Argv сверяется ЗНАЧЕНИЯМИ, а не текстом метода: список читается из
исходника `orchestrator/providers/claude.py` коммита f89bab7c
(`_util.claude_command_argv`) тем же разбором, что и из сегодняшнего
провайдера, — переписанный докстринг или переставленный комментарий
планку не красят, а исчезнувший, переименованный или переставленный флаг
красит. Значение `--setting-sources` берётся из `config` (крутилка
Оператора), а не литералом: поворот крутилки меняет argv одинаково и на
main, и в ветке.

Смоки прогоняются в тех же песочницах, в которых их держат постоянные
регрессии пульта (`tests/test_doctor.py` — для Claude, `tests/sandbox.py`
плюс заглушка резолва инструмента — для Codex): в НАСТОЯЩЕМ корне
рабочей копии `isolation-smoke` красен по причине, к задаче отношения не
имеющей (в worktree задачи нет `.artel/venv`), а `codex-isolation-smoke`
честно пропускается — инструмента `codex` нет в сегодняшнем манифесте.

Зелёный с рождения: обе проверки в своих песочницах зелены и argv
совпадает с main уже сейчас — тест сохранения существующего поведения,
он обязан покраснеть ровно тогда, когда правка требований 4-5 заденет
изоляцию или команду шага.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import doctor, keychain, providers, runner  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_doctor import TmpRootTest as DoctorSandbox  # noqa: E402

STUB_BIN = "/artel-test-stub-bin"
CLAUDE_PROVIDER_SOURCE = "orchestrator/providers/claude.py"


class ClaudeIsolationSmokeStaysGreenTest(DoctorSandbox):

    def test_ac10_claude_isolation_smoke_stays_green(self):
        """`doctor.isolation_smoke()` в песочнице здорового пульта
        отвечает `ok`: маркеры project-/user-слоя не достигли окружения и
        промпта роли, project-/local-слой исключён из resolve-сурсов,
        `--strict-mcp-config` на месте.

        Ловит мутацию: сужение окружения по провайдеру (требование 4)
        написано так, что из окружения шага вымывается HOME или
        CLAUDE_CONFIG_DIR курируемого слоя, — смок ловит это первым же
        пунктом, и роль иначе ушла бы исполняться в user-слой Оператора.
        """
        check = doctor.isolation_smoke()

        self.assertEqual("ok", check.status, check.detail)


class CodexIsolationSmokeStaysGreenTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        env_patch = mock.patch.dict(os.environ, {})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for name in ("CODEX_HOME",) + tuple(
                codex_provider.FORBIDDEN_KEY_ENV_NAMES) + tuple(
                providers.get("claude").secret_env_names()):
            os.environ.pop(name, None)
        for patcher in (
                mock.patch.object(keychain, "token", lambda slot: "tok"),
                mock.patch.object(runner, "declared_tool_path",
                                  lambda name: f"{STUB_BIN}/{name}")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ac10_codex_isolation_smoke_stays_green(self):
        """`doctor.codex_isolation_smoke()` на реально собранных команде
        и окружении шага отвечает `ok`: песочница, выключенная сеть, все
        выключенные функции, курируемый дом и ни одного имени ключа API
        в собранном окружении.

        Ловит мутацию: сужение окружения по провайдеру (требование 4)
        задевает накладку самого Codex — из окружения шага пропадает
        CODEX_HOME либо в него возвращается ambient-дом Оператора, и смок
        краснеет пунктом про дом роли.
        """
        check = doctor.codex_isolation_smoke("developer")

        self.assertEqual("ok", check.status, check.detail)


class ClaudeStepArgvMatchesMainTest(unittest.TestCase):
    """Без песочницы временного корня намеренно: исходник main читается
    `git show` в `config.ROOT`, и подменённый корень увёл бы git из
    репозитория; сборке argv временный корень и не нужен — единственная
    её внешняя зависимость (`declared_tool_path`) подменена здесь же."""

    def test_ac10_claude_step_argv_matches_the_argv_on_main(self):
        """Argv шага роли на Claude (без модели), собранный сегодняшним
        провайдером, совпадает с argv того же провайдера в коммите
        f89bab7c: тот же порядок, те же флаги, то же значение белого
        списка инструментов; нулевой элемент — абсолютный путь из резолва
        манифеста и там, и там.

        Ловит мутацию: правка требования 4 «заодно» трогает команду шага
        Claude — например, снимает `--strict-mcp-config` как «уже
        покрытый домом роли» или переставляет `--model` внутрь списка;
        сравнение со списком main покраснеет на первом же расхождении.
        """
        expected = _util.claude_command_argv(
            _util.main_source(CLAUDE_PROVIDER_SOURCE))
        self.assertIs(
            _util.RESOLVED_CALL, expected[0],
            "на main argv[0] собирался вызовом резолва манифеста — "
            "разбор исходника прочитал что-то другое")

        with mock.patch.object(runner, "declared_tool_path",
                               lambda name: f"{STUB_BIN}/{name}"):
            argv = providers.default().command()
            with_model = providers.default().command("model-x")

        self.assertEqual(f"{STUB_BIN}/claude", argv[0],
                         "argv[0] шага роли — не путь из резолва манифеста")
        self.assertEqual(
            expected[1:], argv[1:],
            f"argv шага роли на Claude разошлось с argv на {_util.MAIN_SHA}")
        self.assertEqual(
            argv + ["--model", "model-x"], with_model,
            "модель обязана оставаться довеском в конце списка, как на main")


if __name__ == "__main__":
    unittest.main()
