"""AC-1: единая функция получения session_id, доступная ВСЕМ командам
оркестратора (не только тем, что уже проходят через `orchestrator/
lease.py`), — единственный источник идентификатора сессии для lease и
для журнала одного и того же вызова.

Красный до реализации: `orchestrator.release.cmd_release` — команда,
которая никогда не проходит через `lease.py` (она не мутирующая в
смысле `lease.run_locked`, см. её модульный докстринг: "`lease.acquire`/
`lease.run_locked`/`parallel_limit.refusal` здесь не вызываются
вовсе"). Сегодня она не резолвит identity вызывающей стороны вовсе:
журнал `lease снят Оператором`, который она пишет, называет только
identity БЫВШЕГО держателя lease (`row['session_id']`, прочитанный из
БД), а не identity сессии, которая СЕЙЧАС выполняет команду `release`.

AC-1 требует, чтобы identity вызывающей сессии была доступна `release.
py` через ТУ ЖЕ функцию, что и `lease.py` — иначе она осталась бы
частной механикой `lease.py`, а не «единой функцией, доступной всем
командам». Тест ниже проверяет это поведенчески, без предположений о
том, в каком именно модуле разработчик оставит саму функцию: `lease.
resolve_session_id` и то, чем резолвит identity `release.cmd_release`,
обязаны читать ОДИН и тот же источник (`ARTEL_SESSION_ID`, уже
задокументированный источник у `lease.resolve_session_id`) и прийти к
одному и тому же значению, которое обязано попасть в журнал `release`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import lease, release, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import LeaseTaskTest, any_step_carries, capture  # noqa: E402


class SharedSessionIdentityTest(LeaseTaskTest):

    def test_ac1_release_resolves_the_same_session_identity_as_lease(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-shared-ac1"}):
            expected = lease.resolve_session_id(None)
            self.assertEqual(expected, "sess-shared-ac1",
                             "предпосылка теста: явный ARTEL_SESSION_ID "
                             "обязан резолвиться лизингом именно в это "
                             "значение (см. tests/test_lease.py)")
            self.insert_lease(self.TASK, "sess-unrelated-holder", 424242,
                              "holder-host", store.now())
            before = len(self.steps())

            capture(release.cmd_release, self.TASK)

        self.assertIsNone(self.lease_row(), "release обязан снять lease "
                          "независимо от AC-1 — это существующее поведение")
        new_steps = self.steps()[before:]
        self.assertTrue(
            any_step_carries(new_steps, expected),
            f"release.cmd_release не назвал в журнале identity сессии, "
            f"выполнившей команду ({expected!r}) — идентификатор, "
            f"полученный `lease.resolve_session_id`, недоступен `release."
            f"py` как единый источник (AC-1): {new_steps}")


if __name__ == "__main__":
    unittest.main()
