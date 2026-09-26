"""AC-14 — 01M3F7BYE82S9AQCBSP1RTQQTR: ни одна проверка doctor не
ослаблена и не удалена.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. Ни одна проверка doctor не ослаблена и не удалена: изменение
статуса строки foreign-provider-secrets идёт только в сторону ужесточения
(warn → fail при чужом секрете в собранном окружении).

Две половины и проверяются по-разному. «Не удалена» — сверкой с деревом
main: ни одно имя строки `doctor` и ни одна функция `check_*` не
исчезли. «Не ослаблена» — сверкой СТАТУСА той единственной строки,
которую задача трогает: в сценарии, где main отвечает `warn`, ветка
обязана отвечать не мягче, а в штатном сценарии — оставаться `ok`.
Базовый статус main не переписан сюда по памяти: планка сначала
убеждается, что в исходнике main эта функция действительно возвращает
`warn`.

Красен до реализации: строка `foreign-provider-secrets` сегодня
отвечает `warn` там, где AC-14 требует ужесточения до `fail`, — сверка
строгости падает; половина «не удалена» при этом зелена (ветка ещё
ничего не удаляла), и это ожидаемо: она сторожит удаление, которого
пока не было.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, doctor, providers, roles, runner  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

ISOLATION_SOURCE = "orchestrator/doctor/isolation.py"
SECRET_VALUE = "znachenie-tokena-operatora"

#: Строгость статуса строки `doctor`: ужесточение — движение вверх.
SEVERITY = {"skip": 0, "ok": 1, "warn": 2, "fail": 3}

#: Исходники main читаются на уровне модуля: тесты ниже идут в песочнице
#: с подменённым `config.ROOT`, а `git show` ходит именно туда.
MAIN_DOCTOR_SOURCES = _util.main_doctor_sources()
MAIN_FOREIGN_CHECK_SOURCE = _util.function_source(
    _util.main_source(ISOLATION_SOURCE), "check_foreign_provider_secrets")


class NoDoctorCheckRemovedTest(unittest.TestCase):

    def test_ac14_no_doctor_check_name_or_function_disappeared(self):
        """Каждое имя строки `doctor` и каждая функция `check_*`,
        существовавшие в `orchestrator/doctor/` на main, есть и в ветке.

        Ловит мутацию: строка, о которой стало неудобно («чужой секрет
        теперь ловится сборкой окружения, проверка лишняя»), удаляется
        вместе со своей функцией — набор `doctor` тихо уменьшается, и
        следующий провайдер со своим секретом попадёт в пульт, где о нём
        никто не говорит.
        """
        gone_names = _util.doctor_check_names(MAIN_DOCTOR_SOURCES) \
            - _util.doctor_check_names()
        gone_functions = _util.doctor_check_functions(MAIN_DOCTOR_SOURCES) \
            - _util.doctor_check_functions()

        self.assertEqual(
            set(), gone_names,
            f"имя(имена) строк doctor исчезли относительно "
            f"{_util.MAIN_SHA}: {sorted(gone_names)}")
        self.assertEqual(
            set(), gone_functions,
            f"функция(и) проверок doctor исчезли относительно "
            f"{_util.MAIN_SHA}: {sorted(gone_functions)}")


class ForeignSecretLineOnlyGetsStricterTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.foreign = providers.get("claude").secret_env_names()
        ambient = mock.patch.dict(os.environ, {})
        ambient.start()
        self.addCleanup(ambient.stop)
        for name in self.foreign:
            os.environ.pop(name, None)
        provider_patch = mock.patch.object(roles, "provider",
                                           lambda role: "codex")
        provider_patch.start()
        self.addCleanup(provider_patch.stop)

    def check_with_step_env(self, env: dict):
        with mock.patch.object(runner, "role_env",
                               lambda role=None, task_id=None: dict(env)):
            return doctor.check_foreign_provider_secrets()

    def test_ac14_the_status_of_the_foreign_secret_line_only_moves_up(self):
        """В сценарии, где на main строка отвечала `warn` (чужой секрет
        достаётся шагу), ветка отвечает статусом не мягче `warn` — и
        именно `fail`; в штатном сценарии строка остаётся `ok`, не
        уползая вниз к `skip`.

        Ловит мутацию: строка «ужесточается» подменой предмета — вместо
        отказа на чужой секрет она начинает честно пропускаться (`skip`)
        там, где сборку окружения подменить не удалось, и Оператор
        читает пропуск как норму.
        """
        self.assertIn(
            '"warn"', MAIN_FOREIGN_CHECK_SOURCE,
            f"на {_util.MAIN_SHA} функция check_foreign_provider_secrets "
            f"не возвращает warn — база сравнения AC-14 не подтверждена "
            f"исходником main")

        # Сценарий воспроизводится ОБОИМИ каналами сразу — ambient
        # Оператора и подменённая сборка окружения: на main строка
        # отвечала на него `warn` (см. assert выше), и сравнивать
        # строгость можно только с тем же сценарием.
        with mock.patch.dict(os.environ, {name: SECRET_VALUE
                                          for name in self.foreign}):
            leaking = self.check_with_step_env(
                {name: SECRET_VALUE for name in self.foreign})
        self.assertGreaterEqual(
            SEVERITY[leaking.status], SEVERITY["warn"],
            f"строка стала мягче, чем была на main (warn): "
            f"{leaking.status} — {leaking.detail}")
        self.assertEqual(
            "fail", leaking.status,
            f"ужесточение по AC-14 — до отказа: {leaking.detail}")

        clean = self.check_with_step_env(
            {"CODEX_HOME": str(config.ROLE_HOME / ".codex")})
        self.assertEqual(
            "ok", clean.status,
            f"штатный случай на main был ok, а стал {clean.status}: "
            f"{clean.detail}")


if __name__ == "__main__":
    unittest.main()
