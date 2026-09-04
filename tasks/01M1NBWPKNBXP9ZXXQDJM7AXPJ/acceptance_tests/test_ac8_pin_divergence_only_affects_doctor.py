"""AC-8 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Расхождение
локального `config.MAIN_BRANCH` (пина) с main артели на origin не
влияет ни на одну проверку конвейера, кроме `doctor` (root-pin): ни на
сверку свежести, ни на merge, ни на чтение артефактов.

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-8.

Красен до реализации: см. докстринги test_ac1/test_ac4 — сегодня
расхождение как раз ВЛИЯЕТ на сверку свежести (ложное `"fresh"` вместо
`"pulled"`), что и есть инцидент 04.09 из «Контекста» SPEC.
`doctor.check_root_pin` при этом уже сегодня корректно детектирует то
же расхождение (`warn`) — эта половина критерия зелёная и ДО фикса, что
и подтверждает: `doctor` не входит в объём правки этой задачи (SPEC «Не
входит»), только сверка свежести рядом с ним ложно молчала. Проверено
прогоном на немодифицированном коде при подготовке файла: `outcome ==
"fresh"` (первая половина красная), `doctor.check_root_pin().status ==
"warn"` (вторая половина уже зелёная).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OriginDivergedSandbox, UPSTREAM_MARKER_REL  # noqa: E402
from orchestrator import doctor  # noqa: E402


class Ac8PinDivergenceOnlyAffectsDoctorTest(OriginDivergedSandbox):

    def test_ac8_pull_unaffected_by_pin_divergence_doctor_still_warns(self):
        """Origin ушёл вперёд локального пина. Одновременно проверяются
        два независимых факта: (а) `_pull_main_or_escalate` корректно
        подтягивает свежий origin — сверка/merge не сбиты расхождением
        пина; (б) `doctor.check_root_pin` — существующая, НЕ тронутая
        этой задачей проверка — продолжает видеть то же расхождение и
        отвечает `warn`, а локальный пин остаётся на месте (ни сверка,
        ни merge не имеют права его двигать).

        Ловит мутацию: правка, которая заодно меняет или обходит
        `doctor.check_root_pin`, либо которая (ошибочно) синхронизирует
        локальный пин побочным эффектом подтяжки — в первом случае
        `warn` пропал бы (SPEC явно требует не трогать эту проверку), во
        втором — `local_pin_sha()` после подтяжки перестал бы совпадать
        с sha ДО неё.
        """
        pin_before = self.local_pin_sha()
        self.advance_origin_only()

        outcome = self.pull()

        self.assertEqual(outcome, "pulled")
        self.assertTrue(self.worktree_file(UPSTREAM_MARKER_REL).exists())
        self.assertEqual(
            self.local_pin_sha(), pin_before,
            "AC-8: сверка/merge не имеют права трогать локальный пин")

        check = doctor.check_root_pin()
        self.assertEqual(
            check.status, "warn",
            f"doctor.check_root_pin обязан по-прежнему видеть расхождение "
            f"пина с main артели на origin — эта проверка не входит в "
            f"объём задачи: {check}")


if __name__ == "__main__":
    import unittest
    unittest.main()
