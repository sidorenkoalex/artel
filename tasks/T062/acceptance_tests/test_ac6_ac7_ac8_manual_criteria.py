"""Приёмочные тесты T062 — AC-6, AC-7, AC-8 (SPEC.md).

AC-1..AC-5 — в `test_ac1_ac2_ac3_ac5_release_command.py` и
`test_ac4_release_frees_limiter_slot.py`.

AC-6 и большая часть AC-7 говорят о СОДЕРЖИМОМ артефакта PLAN.md
конкретного разработчика, которого на момент написания этих тестов ещё
не существует (test_author работает раньше PLAN.md, skills/
test-authoring.md) — тот же случай, что уже решён прецедентом
`tasks/T058/acceptance_tests/test_manual_criteria.py` (AC-5 там: «PLAN.md
несёт подготовленный текст» — тоже содержимое ещё не написанного
документа). Разбор:

- AC-6 целиком о том, что PLAN.md зафиксировал вывод исследования с
  фактурой (файлы/строки/наблюдения) — это Оператор сверяет на приёмке,
  прочитав сам PLAN.md; выдумывать здесь парсинг конкретных фраз
  («статичен»/«продлевается») значило бы навязать разработчику формат
  текста, которого SPEC не диктует (требование 5 отдаёт форму вывода
  разработчику, фиксирует только факт и фактуру).
- AC-7 требует, чтобы `LEASE_STALE_AFTER_SEC` СООТВЕТСТВОВАЛ выводу
  PLAN.md — соответствие сверяет тот же читающий PLAN.md Оператор. Но
  часть критерия, не зависящая от ещё не написанного текста PLAN.md —
  что значение вообще ограничено множеством `{7200, 900}`, которое
  однозначно называют требования 6-7 SPEC, — тестируется здесь напрямую
  (`Ac7ValueIsOneOfSpecPermittedValuesTest`) как страховка от третьего,
  ничем не обоснованного числа.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# AC-6: manual — «PLAN.md несёт зафиксированный вывод исследования —
# продлевается ли heartbeat lease в течение долгого агентного шага, — с
# фактурой (конкретные файлы/строки/наблюдения)» проверяется Оператором
# чтением tasks/T062/PLAN.md на приёмке: содержимое конкретного документа
# конкретного разработчика, которого на момент написания этого файла ещё
# не существует, а формат вывода (что именно считать «зафиксированным» и
# «фактурой») SPEC разработчику не диктует (требование 5) — подгонять
# тест под собственное изобретение формата значило бы проверять не
# критерий, а свою фантазию о нём (skills/test-authoring.md).

# AC-8: manual — «все существующие тесты проходят зелёными» уже покрыто
# `.github/workflows/ci.yml` (джоб «Синтаксис и тесты оркестратора»,
# `unittest discover -s tests -v` на каждый пуш ветки задачи в чистом
# раннере) и требуется гейтом `merge_gate` (`orchestrator/fsm.py`,
# `cmd_approve`) — зелёный статус этого прогона и есть проверка критерия
# (тот же приём, что tasks/T044/acceptance_tests/
# test_lease_readonly_and_doctor.py, tasks/T057/acceptance_tests/
# test_manual_criteria.py, tasks/T060/acceptance_tests/
# test_max_parallel_tasks.py). Повтор всего набора подпроцессом внутри
# acceptance_tests ловил бы окружение машины разработчика, а не дефект
# этой задачи.


import unittest  # noqa: E402

from orchestrator import config  # noqa: E402

SPEC_PERMITTED_VALUES = (7200, 900)


class Ac7ValueIsOneOfSpecPermittedValuesTest(unittest.TestCase):
    """Часть AC-7, не зависящая от текста PLAN.md ещё не написанного:
    `LEASE_STALE_AFTER_SEC` обязан быть одним из двух значений, которые
    называют требования 6 (7200, вывод «heartbeat статичен») и 7 (900,
    вывод «heartbeat продлевается») SPEC — третье, необоснованное число
    критерию не соответствует ни при каком выводе исследования.

    Соответствие КОНКРЕТНОГО из двух значений КОНКРЕТНОМУ выводу PLAN.md
    — manual, см. докстринг модуля.
    """

    def test_ac7_lease_stale_after_sec_is_7200_or_900(self):
        self.assertIn(
            config.LEASE_STALE_AFTER_SEC, SPEC_PERMITTED_VALUES,
            f"orchestrator/config.py::LEASE_STALE_AFTER_SEC="
            f"{config.LEASE_STALE_AFTER_SEC} — SPEC (требования 6-7) "
            f"допускает только {SPEC_PERMITTED_VALUES} в зависимости от "
            f"вывода исследования, зафиксированного в PLAN.md")


if __name__ == "__main__":
    unittest.main()
