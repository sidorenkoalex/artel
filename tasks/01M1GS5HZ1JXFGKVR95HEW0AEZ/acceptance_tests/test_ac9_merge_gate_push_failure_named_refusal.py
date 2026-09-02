"""AC-9 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): упавший push на
входе merge_gate — именованный отказ («голова ветки не в origin, push
не удался: <ошибка>») с журналированием; задача остаётся на merge_gate
без смены состояния и без эскалации, повторный approve после
устранения причины продолжает штатно.

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-9.

Механизм отказа (`sys.exit` или graceful-возврат) SPEC не называет
явно для merge_gate (в отличие от AC-4/AC-5, где требование 3 прямо
отсылает к приёму `fsm_advance.py`) — `orchestrator/fsm_merge_gate.py`
использует ОБА приёма для разных классов отказа: инфраструктурные
провалы `git push` в этом же файле (например, push нового head после
подтяжки, требование 1 T087) — `sys.exit`; отказ по чужой ветке
рабочей копии — graceful `return`. Тест намеренно нейтрален к выбору
реализации: ловит `SystemExit`, если он случился, иначе читает обычный
вывод — критерий проверяет НАБЛЮДАЕМЫЙ результат (состояние, текст
отказа, продолжение после починки), не конкретный питоновский приём.

Красен до реализации: сегодня `_cmd_approve_merge_gate` не проверяет
origin вовсе — с настоящим сломанным origin approve падает на
СУЩЕСТВУЮЩЕМ более позднем шаге (`git pull --ff-only` после checkout
main, уже после того, как мокнутый `ci.branch_status` пропустил бы
зелёный CI) с ДРУГИМ текстом ошибки ("merge упал на git pull
--ff-only"), не с именованной причиной AC-9 — `assertIn` на текст
отказа ниже не находит нужную фразу. Проверено прогоном на
немодифицированном коде при подготовке файла.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import HeadInOriginSandbox  # noqa: E402


class Ac9MergeGatePushFailureTest(HeadInOriginSandbox):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()
        (self.task_dir() / "note.txt").write_text(
            "правка после входа на гейт\n", encoding="utf-8")
        self.expected_head = self.commit_task_dir("правка после входа на гейт")
        self.break_origin_remote()

    def _approve_allow_exit(self) -> str:
        try:
            return self.approve()
        except SystemExit as exc:
            return str(exc)

    def test_ac9_failed_push_is_a_named_refusal_task_stays_on_merge_gate(self):
        """Push проваливается по-настоящему при заходе на approve —
        отказ обязан быть именован ровно так, как называет SPEC, и
        оставить задачу на `merge_gate` без эскалации.

        Ловит мутацию: код, который проверяет origin только на входе В
        merge_gate (раньше, до этого коммита), не в начале КАЖДОГО
        approve — эта задача осталась бы незамеченной, и approve упал
        бы на позднем `git pull --ff-only` с чужим текстом ошибки, не
        с именованной причиной AC-9.
        """
        since = len(self.steps())

        out = self._approve_allow_exit()

        self.assertEqual(
            self.state(), "merge_gate",
            "AC-9: провал push не имеет права сдвинуть задачу дальше "
            "merge_gate")
        self.assertNotEqual(
            self.state(), "escalated",
            "AC-9: провал push сам по себе не эскалирует задачу")
        combined = (out + "\n" + self.journal_tail(since)).lower()
        self.assertIn(
            "голова ветки не в origin, push не удался", combined,
            f"AC-9: отказ обязан быть именован ровно так, как называет "
            f"SPEC: {combined!r}")

    def test_ac9_retry_after_fixing_origin_completes_the_merge(self):
        """После восстановления origin повторный approve доводит
        задачу до `done` тем же путём, что и штатный merge.

        Ловит мутацию: состояние, «залипшее» после первого отказа
        (например, попытка push отмечается как уже предпринятая и не
        повторяется) — второй approve не сдвинул бы задачу дальше
        merge_gate.
        """
        self._approve_allow_exit()
        assert self.state() == "merge_gate", (
            "предпосылка теста: первый approve обязан был отказать")
        self.restore_origin_remote()

        self.approve()

        self.assertEqual(self.state(), "done")
        self.assertEqual(self.origin_branch_sha(), self.expected_head)


if __name__ == "__main__":
    import unittest
    unittest.main()
