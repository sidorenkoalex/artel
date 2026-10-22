"""AC-4: методы разбиения и старые имена — не дольше 10 с (у `test_ac20` — 20 с) на свободной машине; замеры в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md с замерами `--durations` «до»/«после» ещё нет; на свободной машине старые имена длятся дольше порога (замеры ТЗ: 14–26 с, `test_ac20` — 32 с), под нагрузкой замер по условию критерия не берётся. Стабом не провалидирован: при написании загрузка была 17–61 (замер по условию критерия невозможен), PLAN.md читается из ссылки документов.

Замер — настоящий прогон каждого кандидата файла (старые имена и новые
методы) из копии модуля головы, время `TestCase.run` вместе с `setUp`.
Условие критерия «на свободной машине» проверяется в начале каждой части:
средняя загрузка за минуту ниже 4 — пороги утверждаются; иначе замер по
условию критерия невозможен и часть ничего не гоняет (загрузка печатается).
Ловит мутацию у частей — одна на файл: метод со старым именем или доля
исполняет слишком много подслучаев и длится дольше порога.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


class DurationTest(unittest.TestCase):

    def check_part(self, rel, chunk, chunks):
        load = S.load_now()
        print(f"загрузка за минуту в начале части: {load:.2f}")
        if load >= S.FREE_LOAD:
            return
        ac20 = set()
        if rel == S.AUDIT:
            _signal, fail, _stray = S.audit_groups(S.fake_runs(S.AUDIT))
            ac20 = set(fail) | {S.A_FAIL}
        runs = S.real_runs(rel, chunk, chunks)
        for name, run in runs.items():
            limit = S.AC20_LIMIT if name in ac20 else S.SHORT_LIMIT
            with self.subTest(method=name):
                self.assertLessEqual(run.duration, limit,
                                     f"{name}: {run.duration:.1f} с при загрузке {load:.2f}")

    def test_ac4_profile_callers_part0(self):
        """Кандидаты profile_callers (часть 1 из 3) укладываются в 10 с.

        Сценарий: `candidates[0::3]` гоняются по-настоящему при загрузке
        ниже 4; у каждого время не больше 10 с.

        Ловит мутацию: `PultUnchangedTest` разбит на две доли по восемь мест
        — каждая доля около 13 с, порог превышен.
        """
        self.check_part(S.PROFILE, 0, 3)

    def test_ac4_profile_callers_part1(self):
        """Кандидаты profile_callers (часть 2 из 3) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[1::3]`.

        Ловит мутацию: метод со старым именем гоняет все 16 мест — около
        26 с.
        """
        self.check_part(S.PROFILE, 1, 3)

    def test_ac4_profile_callers_part2(self):
        """Кандидаты profile_callers (часть 3 из 3) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[2::3]`.

        Ловит мутацию: доля несёт мест больше, чем укладывается в порог.
        """
        self.check_part(S.PROFILE, 2, 3)

    def test_ac4_outcome_gate_part0(self):
        """Кандидаты outcome_gate (часть 1 из 4) укладываются в 10 с.

        Сценарий: `candidates[0::4]` гоняются по-настоящему при загрузке
        ниже 4; у каждого время не больше 10 с.

        Ловит мутацию: старое имя `test_ac7_rerun_preparation_refusals`
        гоняет все пять подслучаев — около 19 с.
        """
        self.check_part(S.OUTCOME, 0, 4)

    def test_ac4_outcome_gate_part1(self):
        """Кандидаты outcome_gate (часть 2 из 4) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[1::4]`.

        Ловит мутацию: новый метод слил несколько подслучаев — порог
        превышен.
        """
        self.check_part(S.OUTCOME, 1, 4)

    def test_ac4_outcome_gate_part2(self):
        """Кандидаты outcome_gate (часть 3 из 4) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[2::4]`.

        Ловит мутацию: старое имя `test_ac4_*` гоняет все четыре подслучая —
        около 14 с.
        """
        self.check_part(S.OUTCOME, 2, 4)

    def test_ac4_outcome_gate_part3(self):
        """Кандидаты outcome_gate (часть 4 из 4) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[3::4]`.

        Ловит мутацию: старое имя `test_ac7_branch_rerun_red_kinds` гоняет
        пять подслучаев — около 19 с.
        """
        self.check_part(S.OUTCOME, 3, 4)

    def test_ac4_spec_audit_flow_part0(self):
        """Кандидаты spec_audit_flow (часть 1 из 3) — 10 с, у методов `test_ac20` — 20 с.

        Сценарий: `candidates[0::3]` гоняются по-настоящему при загрузке
        ниже 4; методы `test_ac20` (по записям `fail_gate`) — не больше
        20 с, прочие — не больше 10 с.

        Ловит мутацию: `test_ac20_…` оставлен с обеими формами — около 32 с.
        """
        self.check_part(S.AUDIT, 0, 3)

    def test_ac4_spec_audit_flow_part1(self):
        """Кандидаты spec_audit_flow (часть 2 из 3) — 10 с, у методов `test_ac20` — 20 с.

        Сценарий: как часть 1, `candidates[1::3]`.

        Ловит мутацию: `test_ac9` за старым именем гоняет все подслучаи —
        около 24 с.
        """
        self.check_part(S.AUDIT, 1, 3)

    def test_ac4_spec_audit_flow_part2(self):
        """Кандидаты spec_audit_flow (часть 3 из 3) — 10 с, у методов `test_ac20` — 20 с.

        Сценарий: как часть 1, `candidates[2::3]`.

        Ловит мутацию: доля категорий `test_ac9` несёт все категории и
        фиксированные подслучаи — порог превышен.
        """
        self.check_part(S.AUDIT, 2, 3)

    def test_ac4_pytest_own_places_part0(self):
        """Кандидаты pytest_own_places (часть 1 из 3) укладываются в 10 с.

        Сценарий: `candidates[0::3]` гоняются по-настоящему при загрузке
        ниже 4; у каждого время не больше 10 с.

        Ловит мутацию: `test_ac6_…` за старым именем гоняет 2 режима × 8
        мест — около 24 с.
        """
        self.check_part(S.OWN, 0, 3)

    def test_ac4_pytest_own_places_part1(self):
        """Кандидаты pytest_own_places (часть 2 из 3) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[1::3]`.

        Ловит мутацию: `test_ac3_home_removed…` за старым именем гоняет
        все места в обоих режимах — около 19 с.
        """
        self.check_part(S.OWN, 1, 3)

    def test_ac4_pytest_own_places_part2(self):
        """Кандидаты pytest_own_places (часть 3 из 3) укладываются в 10 с.

        Сценарий: как часть 1, `candidates[2::3]`.

        Ловит мутацию: доля несёт мест больше, чем укладывается в порог.
        """
        self.check_part(S.OWN, 2, 3)

    def test_ac4_plan_has_durations_before_and_after(self):
        """PLAN.md несёт замеры `--durations` «до» и «после» по каждому из четырёх файлов и загрузку.

        Сценарий: PLAN.md из ссылки документов задачи называет
        `--durations`, «до» и «после», имя каждого из четырёх файлов зоны,
        неразбиваемые `test_ac17_reject_does_not_reset_return_counter` и
        `test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` и
        значение загрузки (слово «загрузк…» рядом с числом).

        Ловит мутацию: замер сделан по одному файлу или без значения
        загрузки — имени файла или загрузки в PLAN нет.
        """
        plan = S.plan_text()
        self.assertIn("--durations", plan)
        self.assertRegex(plan, r"(?i)\bдо\b")
        self.assertRegex(plan, r"(?i)\bпосле\b")
        for rel in S.ZONE:
            self.assertIn(Path(rel).stem, plan, rel)
        for name in ("test_ac17_reject_does_not_reset_return_counter",
                     "test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit"):
            self.assertIn(name, plan)
        self.assertRegex(plan, r"(?is)загрузк.{0,80}?\d+[.,]\d+")


if __name__ == "__main__":
    unittest.main()
