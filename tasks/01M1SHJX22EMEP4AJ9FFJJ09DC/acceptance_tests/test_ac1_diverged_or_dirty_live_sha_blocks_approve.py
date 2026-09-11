"""AC-1 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md) — отрицательная сторона
той же сверки, что и `test_ac1_matching_live_sha_lets_approve_through.py`:
«...сверяет его с зафиксированным на последнем переходе sha и чистотой
рабочей копии/артефактной ветки» — расхождение или грязная копия обязаны
НЕ пропускать approve.

Зелёный с рождения: сегодняшний `confirm_fixation` при `sha is None`
безусловно возвращает `False` (печатает «approve требует sha»),
НЕЗАВИСИМО от того, что вернула бы сверка — расхождение/грязная копия
здесь совпадают по НАБЛЮДАЕМОМУ исходу (`False`) что до, что после
реализации AC-1, поэтому файл зелёный с рождения, а не показывает
отсутствующую фичу. Ценность теста — не в сегодняшней красноте, а в
том, что он ЗАФИКСИРУЕТ этот исход как планку: реализация AC-1,
добавляющая реальное сравнение, не имеет права заодно случайно начать
пропускать approve на расхождении/грязной копии (например, перепутав
`==` на `!=` или забыв про `clean`). Прогнано: оба метода уже проходят
на сегодняшнем коде.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fixation, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class ConfirmFixationDivergedOrDirtyLiveShaBlocksApproveTest(TmpRootTest):

    TASK = "T900"
    FIXED_SHA = "a" * 40
    OTHER_SHA = "b" * 40

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача", "spec_gate",
                          "task/t900-x", config.DEFAULT_TARGET, 50.0)
        store.update_task(self.conn, self.TASK, fixed_sha=self.FIXED_SHA)

    def confirm_or_refused(self, sha) -> bool:
        """`confirm_fixation`, но именованный отказ — не обязательно
        `False` (SPEC не предписывает механизм отказа: и мягкий возврат
        `False`, и `sys.exit` с текстом отказа — оба «не пропускают
        approve»; `cmd_approve`/AC-3 уже сверяют текст отказа отдельно,
        здесь важен только сам факт «не пропустило»)."""
        try:
            return fsm.confirm_fixation(self.conn, self.TASK, sha)
        except SystemExit:
            return False

    def test_ac1_diverged_live_sha_does_not_let_approve_through(self):
        """Живое чтение расходится с `tasks.fixed_sha` — сверка обязана
        это заметить и НЕ пропустить approve дальше, доказывая, что
        сравнение (когда оно появится) идёт именно с колонкой `tasks.
        fixed_sha`, а не вслепую пропускает любое непустое значение.

        Ловит мутацию: реализация AC-1, которая при `sha is None`
        возвращает `True`, если `fixation.read` вернула хоть какое-то
        непустое значение (без сверки с `tasks.fixed_sha`), — тест
        обнаружит это, так как `OTHER_SHA` заведомо не совпадает с
        `FIXED_SHA`, но результат остался бы `True`.
        """
        with mock.patch.object(fixation, "read",
                               return_value=(self.OTHER_SHA, True)):
            result = self.confirm_or_refused(None)

        self.assertFalse(
            result, "расхождение живого sha с зафиксированным не может "
            "пропускать approve молча")

    def test_ac1_dirty_copy_with_matching_sha_does_not_let_approve_through(self):
        """Sha совпадает, но копия грязная (`clean=False`) — сверка
        обязана учитывать чистоту рабочей копии/артефактной ветки, не
        только сам sha.

        Ловит мутацию: если проверка чистоты забудется в реализации AC-1
        (сравнение только по `current == fixed`), грязная, но
        совпадающая по sha копия ошибочно пропустила бы approve.
        """
        with mock.patch.object(fixation, "read",
                               return_value=(self.FIXED_SHA, False)):
            result = self.confirm_or_refused(None)

        self.assertFalse(result, "грязная копия не может пропускать approve")


if __name__ == "__main__":
    unittest.main()
