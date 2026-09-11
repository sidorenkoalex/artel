"""Приёмочные тесты 01M290PYPV5T2NFW1Y0HB8BD6E — AC-1, AC-2, AC-4:
эскалация `in_dev` по конфликту подтяжки метит задачу так, что цикл
`auto`, вернувшись из `escalated`, обязан позвать роль (developer) СНОВА
вместо немедленного повтора предварительного advance по тому же PLAN.md
(П1 копилки 11.09 — иначе разрешать конфликт некому), и не жжёт эскалации
по кругу, если роль не смогла продвинуть задачу.

Красен до реализации: конфликт подтяжки эскалирует `in_dev` без единого
предшествующего входа в `in_dev` через журнал (песочница ставит
`tasks.state` напрямую, тем же приёмом, что и `LightTransitionSandbox.
advance_from_in_dev`) — единственная запись `state -> in_dev`, которую
`auto._role_step_since_state_entry` видит ПОСЛЕ возврата из `escalated`,
несёт фиксированный текст `_approve_escalated` («эскалация разрешена,
продолжаем»), уже входящий в `_ESCALATED_RETURN_DETAILS` и потому
пропускаемый при поиске анкера — рубеж деградирует на вырожденный случай
«сверять нечем» (`True, None`) и НЕ блокирует пред-advance ни для какого
основания эскалации, включая конфликт подтяжки: сегодняшний код не
различает основания эскалации вовсе. Прогон перед написанием файла
подтвердил: `test_ac1_...` и `test_ac2_...` падают именно на этом (гейт
не блокирует, второй merge случается раньше шага developer), `test_ac4_...`
падает потому, что фразы «предварительный advance дважды упёрся» нет ни в
одном выводе `auto` — кода стоп-крана требования 2 в репозитории ещё нет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PullConflictAutoSandbox  # noqa: E402
from orchestrator import auto, store  # noqa: E402


class ConflictEscalationMarksTheTaskTest(PullConflictAutoSandbox):
    """AC-1: эскалация `in_dev` по конфликту подтяжки помечает задачу
    признаком «нужен шаг роли до следующего предварительного advance» —
    наблюдается через тот самый узел, которым этот признак обязан читаться
    (`auto._role_step_since_state_entry`, «тем же приёмом», SPEC
    требование 1): без пометки рубеж после возврата из такой эскалации
    вырождается («сверять нечем») и НЕ требует нового шага developer, с
    пометкой — требует."""

    def test_ac1_pull_conflict_escalation_leaves_a_marker_the_gate_reads(self):
        """Конфликт подтяжки эскалирует `in_dev`, Оператор отвечает и
        возвращает approve — после возврата гейт пред-advance обязан
        требовать НОВЫЙ шаг developer (`ran=False`), а не считать задачу
        готовой по уже написанному PLAN.md.

        Ловит мутацию: точка эскалации конфликта подтяжки (`pull.py`/
        `fsm._pull_main_or_escalate`) не оставляет отличимого признака —
        `_role_step_since_state_entry` не находит анкера вовсе (единственная
        запись `state -> in_dev` после возврата несёт пропускаемый
        `_ESCALATED_RETURN_DETAILS`-текст) и по вырожденному случаю
        возвращает `ran=True` — `assertFalse` ниже поймает это.
        """
        conn = store.db()

        self.escalate_in_dev_via_pull_conflict()
        self.assertEqual(self.state(), "escalated",
                         "неразрешаемый конфликт подтяжки обязан эскалировать")

        self.approve()
        self.assertEqual(
            self.state(), "in_dev",
            "approve не вернул задачу в in_dev — сценарий не воспроизведён")

        ran, _detail = auto._role_step_since_state_entry(
            conn, self.TASK, "in_dev", "developer")

        self.assertFalse(
            ran, "эскалация конфликта подтяжки не пометила задачу — гейт "
            "пред-advance не требует нового шага developer после возврата")


class NextAutoCallRunsTheRoleNotPreAdvanceTest(PullConflictAutoSandbox):
    """AC-2: после возврата из `escalated` по основанию AC-1 следующий
    `auto` начинает со шага роли текущего состояния, не с `_pre_advance_
    step` — иначе разрешать повторяющийся конфликт некому (П1 копилки)."""

    def test_ac2_developer_runs_before_pre_advance_retries_the_same_pull(self):
        """auto, вызванный сразу после возврата, обязан позвать developer
        РАНЬШЕ, чем предварительный advance повторно наткнётся на тот же
        неизменившийся конфликт подтяжки.

        Ловит мутацию: чтение маркера AC-1 отключено (гейт пред-advance
        снова не блокирует) — `_pre_advance_step` вызывает `fsm.cmd_advance`
        первым же действием итерации, тот сразу переэскалирует БЕЗ единого
        вызова роли (`role=None` для `escalated` останавливает цикл `auto`
        раньше, чем FakeRun хоть раз позовётся) — `role_run_count()`
        останется 0 вместо ожидаемой 1.
        """
        self.escalate_in_dev_via_pull_conflict()
        self.approve()
        self.assertEqual(self.state(), "in_dev")

        self.auto()

        self.assertEqual(
            self.role_run_count(), 1,
            "developer не был вызван после возврата из эскалации конфликта "
            "подтяжки — auto сразу повторил предварительный advance")


class RepeatedSameBasisEscalationStopsNamedTest(PullConflictAutoSandbox):
    """AC-4: повторный вход в `escalated` из предварительного advance с тем
    же основанием подряд, без единого шага роли между двумя эскалациями, —
    не новая эскалация, а остановка `auto` именованной причиной
    «предварительный advance дважды упёрся в <основание> без шага роли —
    решение Оператора» (стоп-кран, не даёт циклу жечь эскалации по кругу,
    SPEC требование 2)."""

    ROUNDS = 6

    def test_ac4_auto_stops_named_instead_of_looping_escalations_forever(self):
        """Конфликт подтяжки не меняется ни разу (developer не может его
        разрешить сам), Оператор раз за разом отвечает и повторяет approve
        + auto — цикл ОБЯЗАН сойтись: остановиться именованной причиной
        требования 2 за ограниченное число раундов, не эскалировать
        бесконечно.

        Ловит мутацию: стоп-кран требования 2 не реализован вовсе (или не
        достижим) — `auto` продолжает эскалировать на каждом раунде без
        единого появления фразы «предварительный advance дважды упёрся» —
        цикл `for` исчерпает `ROUNDS`, `stop_output` останется `None`, и
        `assertIsNotNone` упадёт.
        """
        self.escalate_in_dev_via_pull_conflict()

        stop_output = None
        for _ in range(self.ROUNDS):
            self.assertEqual(self.state(), "escalated")
            self.approve()
            self.assertEqual(self.state(), "in_dev")

            out = self.auto()
            if "предварительный advance дважды упёрся" in out:
                stop_output = out
                break
            self.assertEqual(
                self.state(), "escalated",
                "auto не остановился именованной причиной requirement 2 и "
                "не переэскалировал тем же основанием — сценарий разошёлся "
                "с ожиданием (конфликт не меняется ни разу)")

        self.assertIsNotNone(
            stop_output, f"auto не остановился именованной причиной "
            f"requirement 2 за {self.ROUNDS} раундов повторной эскалации "
            f"одного и того же конфликта")
        self.assertGreaterEqual(
            self.role_run_count(), 1,
            "стоп-кран сработал раньше, чем роль получила хоть один шанс "
            "разрешить конфликт (requirement 1)")
        self.assertEqual(
            self.state(), "escalated",
            "именованная остановка requirement 2 обязана оставить задачу "
            "в escalated, не тихо продвигать её дальше")


if __name__ == "__main__":
    import unittest
    unittest.main()
