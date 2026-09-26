"""AC-6..AC-10: предполётная проверка `codex-chatgpt-auth` вместо
`codex-api-key` — состав набора, вызов `codex login status` домом роли,
условие `ok`, отсутствие вывода CLI в строке и область действия.

Красен до реализации: проверки `codex-chatgpt-auth` в пульте нет —
`CodexProvider.check_token` зовёт `doctor.check_codex_api_key`, и та
смотрит только наличие ключа в слоте keychain; `codex login status` не
зовёт никто, поэтому тесты AC-6..AC-9 ниже падают на отсутствующей
проверке (первым — на имени строки в наборе предполёта).

Тест AC-10 (область действия строки) до реализации зелён вырожденно —
строки, которая могла бы напечататься лишней, ещё нет; различающим он
становится вместе с реализацией, и держит её от подключения проверки в
общий набор `doctor`. Красноту файла честной делают остальные четыре
теста.
"""
import inspect
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config, doctor, keychain, providers  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# Вывод `codex login status` в трёх состояниях; в КАЖДОЙ строке — маркер,
# чтобы эхо любой строки вывода в текст проверки было видно (AC-9).
OUT_MARKER = "VYVOD-CLI-STDOUT-01M3EK"
ERR_MARKER = "VYVOD-CLI-STDERR-01M3EK"
LOGGED_IN_CHATGPT = f"Logged in using ChatGPT {OUT_MARKER}"
LOGGED_IN_API_KEY = f"Logged in using an API key {OUT_MARKER}"
NOT_LOGGED_IN = f"Not logged in {OUT_MARKER}"
STDERR_NOISE = f"{ERR_MARKER}: warning from cli"

CODEX_VERSION = "0.155.1"


class _Runs:
    """Подмена `subprocess.run` на время проверки: отвечает на
    `codex --version`, `claude --version` и на `codex … login status`.

    Настоящий `codex` на машине прогона не нужен и не запускается ни
    разу — ни одного живого вызова CLI в шаге нет (SPEC, «Не входит»).
    """

    def __init__(self, stdout=LOGGED_IN_CHATGPT, stderr=STDERR_NOISE,
                 returncode=0, raises=None):
        self.stdout, self.stderr = stdout, stderr
        self.returncode, self.raises = returncode, raises
        self.login_calls = []

    def __call__(self, args, **kwargs):
        argv = [str(item) for item in args]
        name = Path(argv[0]).name
        if "login" in argv:
            self.login_calls.append((argv, kwargs))
            if self.raises is not None:
                raise self.raises
            return subprocess.CompletedProcess(argv, self.returncode,
                                               self.stdout, self.stderr)
        if name == "codex":
            return subprocess.CompletedProcess(argv, 0, f"{CODEX_VERSION}\n", "")
        if name == "claude":
            return subprocess.CompletedProcess(
                argv, 0, f"{config.CLI_VERSION_PIN}\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")


class ChatgptAuthCheckTest(TmpRootTest):
    """Проверка подписочного входа — требование 4."""

    def setUp(self):
        super().setUp()
        _util.drop_ambient(self, *_util.CLAUDE_SECRETS,
                           *_util.FORBIDDEN_ENV_NAMES)
        _util.patch(self, keychain, "token", lambda slot: "tok-podpiski")
        _util.patch(self, doctor.shutil, "which",
                    lambda name, *a, **kw: f"{_util.STUB_BIN}/{name}")
        _util.stub_tool_path(self)

    def preflight(self, runs):
        """Набор предполёта провайдера на подменённом `subprocess.run`."""
        with mock.patch.object(doctor.subprocess, "run", runs):
            return providers.get("codex").preflight("developer")

    def auth_line(self, runs):
        """Строка `codex-chatgpt-auth` из набора предполёта — набор
        собирается РОВНО ОДИН раз: повторный вызов ради текста сообщения
        добавил бы второй подпроцесс `codex login status` и сломал бы
        счёт вызовов в AC-7."""
        checks = self.preflight(runs)
        lines = [c for c in checks if c.name == _util.AUTH_CHECK]
        self.assertEqual(len(lines), 1, [c.name for c in checks])
        return lines[0]

    def test_ac6_the_api_key_check_is_replaced_keeping_the_rest_of_the_set(self):
        """На месте `codex-api-key` стоит блокирующая строка
        `codex-chatgpt-auth`, а состав и порядок остальных строк
        предполёта провайдера (CLI найден, версия CLI, дом роли) — те же;
        имени `codex-api-key` нет ни в одном исходе и ни в одном файле
        кода пульта.

        Ловит мутацию: новая проверка ДОБАВЛЕНА рядом со старой («ключ
        пусть тоже проверяется, вдруг понадобится») — предполёт краснеет
        на отсутствующем ключе, которого шагу больше никто не передаёт, и
        роль на Codex не стартует вовсе. Вторая мутация того же теста:
        строка вставлена в начало набора и вытесняет `codex-cli-found` —
        Оператор читает отказ авторизации там, где CLI просто не
        установлен.
        """
        runs = _Runs()

        names = [c.name for c in self.preflight(runs)]

        self.assertEqual(names, ["codex-cli-found", "codex-cli-version",
                                 _util.AUTH_CHECK, "codex-role-home"])
        for scenario in (_Runs(), _Runs(returncode=1),
                         _Runs(stdout=NOT_LOGGED_IN)):
            with self.subTest(returncode=scenario.returncode):
                self.assertNotIn(_util.OLD_CHECK,
                                 [c.name for c in self.preflight(scenario)])
        failing = self.auth_line(_Runs(returncode=1))
        self.assertEqual(failing.status, "fail", failing.detail)
        for path in _util.pult_code_files():
            with self.subTest(file=path.name):
                self.assertNotIn(_util.OLD_CHECK,
                                 path.read_text(encoding="utf-8"),
                                 str(path.relative_to(_util.REPO_ROOT)))

    def test_ac7_the_check_calls_login_status_with_the_role_home_and_the_step_overrides(self):
        """Проверка зовёт `codex login status` с `HOME`/`CODEX_HOME`
        курируемого дома роли и с теми же двумя переопределениями
        авторизации, что несёт команда шага, под таймаутом; истёкший
        таймаут и незапустившийся CLI дают `fail` с названной причиной,
        а не исключение наружу.

        Ловит мутацию: вызов собран без окружения дома роли (CLI читает
        `~/.codex` Оператора) либо без переопределений авторизации —
        `codex login status` тогда отвечает про ЛИЧНЫЙ вход Оператора или
        про способ авторизации, отличный от того, каким пойдёт шаг, и
        зелёная строка `doctor` доказывает не то, что нужно. Вторая
        мутация: вызов без `timeout=` — висящий CLI держит предполёт
        шага, а поднятый наружу `TimeoutExpired`/`OSError` роняет `doctor`
        трейсбеком вместо названной причины.
        """
        runs = _Runs()
        deployed = config.ROLE_HOME / ".codex"
        step_overrides = _util.config_overrides(_util.codex_command())

        self.auth_line(runs)

        self.assertEqual(len(runs.login_calls), 1, runs.login_calls)
        argv, kwargs = runs.login_calls[0]
        self.assertEqual(Path(argv[0]).name, "codex", argv)
        self.assertIn("login", argv, argv)
        self.assertIn("status", argv, argv)
        self.assertLess(argv.index("login"), argv.index("status"), argv)
        env = kwargs.get("env") or {}
        self.assertEqual(env.get("HOME"), str(config.ROLE_HOME), sorted(env))
        self.assertEqual(env.get("CODEX_HOME"), str(deployed), sorted(env))
        for key, _value in _util.AUTH_OVERRIDES:
            with self.subTest(key=key):
                self.assertIn(key, step_overrides, step_overrides)
                self.assertTrue(
                    _util.carries_pair(argv, key, step_overrides[key]), argv)
        timeout = kwargs.get("timeout")
        self.assertIsNotNone(timeout, kwargs)
        self.assertGreater(timeout, 0)

        for title, raises in (
                ("таймаут", subprocess.TimeoutExpired(cmd="codex", timeout=1)),
                ("CLI не запустился", OSError("нет такого файла"))):
            with self.subTest(scenario=title):
                line = self.auth_line(_Runs(raises=raises))

                self.assertEqual(line.status, "fail", line.detail)
                self.assertTrue(line.detail.strip(), line)

    def test_ac8_ok_needs_both_a_zero_exit_code_and_a_confirmed_chatgpt_login(self):
        """`ok` — только код выхода 0 И подтверждённый вход ChatGPT:
        ненулевой код — `fail`; код 0 без подтверждения (не вошёл либо
        вошёл ключом API) — тоже `fail`.

        Ловит мутацию: вердикт считается по одному коду выхода — `codex
        login status` отвечает нулём и на «Not logged in», и на вход
        ключом API (тот самый ключ без баланса, с которым 22.09 живой
        запуск получил 401), и зелёная строка `doctor` доказывала бы
        авторизацию, которой у шага нет.
        """
        ok = self.auth_line(_Runs(stdout=LOGGED_IN_CHATGPT, returncode=0))
        self.assertEqual(ok.status, "ok", ok.detail)

        for title, runs in (
                ("ненулевой код выхода",
                 _Runs(stdout=LOGGED_IN_CHATGPT, returncode=1)),
                ("код 0, вход не выполнен",
                 _Runs(stdout=NOT_LOGGED_IN, returncode=0)),
                ("код 0, вход ключом API",
                 _Runs(stdout=LOGGED_IN_API_KEY, returncode=0))):
            with self.subTest(scenario=title):
                line = self.auth_line(runs)

                self.assertEqual(line.status, "fail", line.detail)

    def test_ac9_the_line_hides_cli_output_and_names_both_one_time_operator_steps(self):
        """Ни в одном исходе строка не несёт вывода CLI (ни stdout, ни
        stderr); её отказ называет оба однократных шага Оператора —
        указатель связки ключей для дома роли и команду входа, — а про
        остаток лимита подписки сказано либо в самой строке, либо в
        `docs/stack.md`.

        Ловит мутацию: причину отказа берут прямо из вывода CLI («так
        Оператору понятнее») — `codex login status` печатает адрес
        связки ключей и состояние авторизации, то есть строка `doctor`
        начинает выносить в лог сведения об аутентификации. Вторая
        мутация: отказ назван общо («вход не выполнен»), без обоих
        однократных шагов, — Оператор получает красную строку без
        рецепта, а шаг 22.09 показал, что без указателя связки ключей
        вход не сохраняется вовсе (`persist_failed`).
        """
        details = []
        for runs in (_Runs(), _Runs(returncode=1), _Runs(stdout=NOT_LOGGED_IN),
                     _Runs(stdout=LOGGED_IN_API_KEY),
                     _Runs(raises=subprocess.TimeoutExpired(cmd="codex",
                                                            timeout=1)),
                     _Runs(raises=OSError("нет такого файла"))):
            line = self.auth_line(runs)
            details.append(line.detail)
            with self.subTest(status=line.status, detail=line.detail[:40]):
                self.assertNotIn(OUT_MARKER, line.detail)
                self.assertNotIn(ERR_MARKER, line.detail)

        failing = _util.squashed(self.auth_line(_Runs(stdout=NOT_LOGGED_IN)).detail)
        self.assertIn("default-keychain", failing)
        self.assertIn("codex login", failing)

        stack_section = ""
        if _util.STACK_DOC.is_file():
            from scripts import guard
            stack_section = guard.section_body(
                _util.STACK_DOC.read_text(encoding="utf-8"),
                _util.STACK_DOC_SECTION)
        about_limit = _util.squashed("\n".join(details) + "\n" + stack_section)
        self.assertIn("лимит", about_limit)
        self.assertTrue(
            any(phrase in about_limit
                for phrase in ("не доказыва", "не подтвержда", "не гарантир",
                               "не проверя")),
            "ни в строке, ни в docs/stack.md не сказано, что остаток "
            "лимита подписки проверка не доказывает")

    def test_ac10_a_pult_without_a_codex_role_neither_prints_the_line_nor_calls_the_cli(self):
        """На пульте, где ни одна agent-роль не идёт на `codex`, строки
        `codex-chatgpt-auth` в выводе `doctor` нет и `codex login status`
        не зовётся ни одним подпроцессом — строка приходит ровно из
        `CodexProvider.preflight`.

        Ловит мутацию: проверка подключена к общему набору `doctor`
        (`all_checks`/`preflight_checks`) вместо предполёта провайдера —
        КАЖДЫЙ прогон диагностики на пульте без Codex платит подпроцессом
        `codex login status` и печатает красную строку про авторизацию
        инструмента, которым никто не пользуется.
        """
        runs = _Runs()
        target = config.DEFAULT_TARGET

        with mock.patch.object(doctor.subprocess, "run", runs):
            grouped = doctor.provider_preflight_checks()
            step = doctor.preflight_checks("developer", target)

        self.assertNotIn(_util.AUTH_CHECK, grouped, sorted(grouped))
        self.assertNotIn(_util.AUTH_CHECK, [c.name for c in step],
                         [c.name for c in step])
        self.assertEqual(runs.login_calls, [], runs.login_calls)
        self.assertNotIn("chatgpt",
                         inspect.getsource(doctor.all_checks).lower())


if __name__ == "__main__":
    unittest.main()
