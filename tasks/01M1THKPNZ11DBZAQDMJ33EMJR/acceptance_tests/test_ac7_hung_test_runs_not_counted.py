"""Приёмочный тест AC-7 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-7. Инцидент сторожа зависших прогонов тестов
(`doctor.check_hung_test_runs`) не увеличивает счётчик ни одного класса
стоп-крана.

`doctor.check_hung_test_runs` заводит `kind=incident, source=
doctor.hung_test_runs` НАПРЯМУЮ через `alerts.raise_alert` — не через
журнал `steps` и не через ни одну из двух точек вызова требования 3
(`orchestrator/runner.py`, классификация отказа/таймаут шага). Кандидаты
процессов подделаны подменой `doctor._find_hung_test_runs` (единственный
разумный шов без настоящих зависших процессов ОС) — фейковый `task_id`
не обязан существовать в `tasks` (`store.task_target` деградирует к
`config.DEFAULT_TARGET`, тот же приём, что и настоящий сторож для
осиротевшего процесса).

Красен до реализации: НЕТ — «зелёный с рождения». Счётчика стоп-крана
волны, который мог бы перепутать это с классифицированным
отказом/таймаутом, в коде нет вовсе, а сам `check_hung_test_runs` уже
сегодня заводит алерт СВОИМ путём (`source=doctor.hung_test_runs`),
никак не пересекающимся с журналом «agent failure classified»/«agent
run TIMEOUT». Тест ловит регрессию: реализацию, которая по ошибке
подключит источник `doctor.hung_test_runs` (или вообще любой `kind=
incident`) к подсчёту стоп-крана волны вместо того, чтобы читать
исключительно журнал `steps` по двум названным требованием 3 точкам.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402


class Ac7HungTestRunsNotCountedTest(WaveBreakerSandbox):

    def test_ac7_three_hung_test_run_incidents_raise_no_wave_breaker_alert(self):
        """Три разных зависших прогона тестов (три разных фейковых
        `task_id`) обнаруживает `doctor.check_hung_test_runs` — каждый
        заводит СВОЙ `kind=incident` (`source=doctor.hung_test_runs`), но
        ни один из них не должен посчитаться стоп-краном волны никакого
        класса.

        Ловит мутацию: подсчёт стоп-крана волны сканирует ВСЕ открытые
        `kind=incident` алерты (а не журнал `steps` двух точек требования
        3) — тогда три разных `doctor.hung_test_runs` уже сами по себе
        достигли бы `config.WAVE_BREAKER_TASKS=3` и подняли бы алерт
        стоп-крана волны здесь.
        """
        candidates = [
            {"pid": 1001 + i, "age": 999, "cwd": f"/fake/worktree-{i}",
             "task_id": f"FAKE-HUNG-{i}"}
            for i in range(3)
        ]
        # `check_hung_test_runs` авто-подтверждает алерты, чей pid не
        # живой (`_auto_ack_gone`/`_hung_test_run_alert_live`) — фейковые
        # pid 1001..1003 почти наверняка не живые процессы этой машины и
        # были бы закрыты в ТОМ ЖЕ вызове раньше, чем тест успел бы их
        # увидеть. Подмена держит все три «висящими» — сценарий «сейчас
        # открыты три инцидента сторожа», который и проверяет критерий.
        with mock.patch.object(doctor, "_find_hung_test_runs",
                               return_value=candidates), \
                mock.patch.object(doctor, "_hung_test_run_alert_live",
                                  return_value=True):
            results = doctor.check_hung_test_runs(store.db())

        self.assertEqual(len(results), 3, "сторож обязан был найти все три")
        hung_alerts = [r for r in self.open_incident_alerts()
                      if r["source"] == "doctor.hung_test_runs"]
        self.assertEqual(len(hung_alerts), 3,
                         "сам сторож заводит алерт по каждому кандидату — "
                         "сценарий действительно воспроизведён")

        found = self.wave_breaker_alerts()

        self.assertEqual(
            found, [],
            f"инциденты сторожа зависших прогонов тестов не должны "
            f"увеличивать счётчик ни одного класса стоп-крана волны; "
            f"найдено: {[r['message'] for r in found]}")


if __name__ == "__main__":
    unittest.main()
