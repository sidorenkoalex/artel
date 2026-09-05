"""AC-1, AC-3, AC-4, AC-5 (tasks/01M1RA0N6FCFEQBB82K58GM12X/SPEC.md): гейт
ёмкости diff на переходе `in_dev -> review` (`fsm_advance._capacity_gate_
refuses`) обязан мерить размер diff БЕЗ `tasks/<id>/` (артефакты, включая
залоченную планку) — большая копия артефактов задачи в кодовой ветке не
имеет права раздувать меру и отклонять переход, который прошёл бы по
одному коду (AC-1); когда отказ всё же случается, он называет обе
цифры — код и исключённые артефакты (AC-3); код сам по себе крупнее
потолка отклоняет переход, как и раньше, до этой задачи (AC-5, регресс-
страховка относительно AC-12/AC-16 tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X).

`_sandbox.GitFeatureBranchSandbox` — настоящий git-репозиторий
(`tests.sandbox.RealGitSandbox`), не подмена `gitcmd.git`: предмет
проверки — байтовый размер diff под РЕАЛЬНЫМ `git diff main...branch`.
Пример реализации в SPEC (`git diff main...HEAD -- . ':!tasks/'`) — один
из вариантов; тест не завязан на конкретный вызов git внутри гейта,
только на измеримый результат (отказ/проход, содержимое сообщения).

Красен до реализации: гейт сегодня (`orchestrator/fsm_advance.py::
_capacity_gate_refuses`) меряет `git diff main...branch` целиком, без
исключения `tasks/<id>/`, и сообщение отказа несёт одну цифру — Ac1*/
Ac3*Test ниже видят отказ там, где по требованию его быть не должно,
либо не находят вторую цифру в сообщении.

Зелёный с рождения: Ac5CodeAloneOverCapStillRefusesTest — код сам по
себе крупнее потолка отклоняет переход уже сегодня (AC-12 tasks/
01M1GCN1FPSC1A6WK9WD1Q1V8X), это требование задача не меняет; тест здесь
— страховка, что исключение `tasks/<id>/` этот путь не задевает.
"""
# AC-7: manual — «существующие тесты гейта ёмкости и ревью-пакета
# (01M1GCN1FPSC1A6WK9WD1Q1V8X, T029, регрессия №10) остаются зелёными
# без ослабления» проверяется полным прогоном `tests/` на CI; test_author
# не гоняет здесь полный набор `tests/` (skills/test-authoring.md,
# решение Оператора 05.09) — планка этого файла и test_ac2_ac6_
# review_package_excludes_tasks_dir.py покрывает содержательную часть
# критерия (AC-1..AC-6) напрямую.

import io
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, fsm_advance  # noqa: E402
from _sandbox import GitFeatureBranchSandbox  # noqa: E402

CAP = config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES  # требование 1: порог не меняется


def _plausible_byte_counts(diff_text: str) -> set:
    """Байтовый размер `diff_text` «как есть» и после `.strip()` — тот же
    разбор хвостового перевода строки, что `review.git_diff_part` уже
    делает для diff'а (`res.stdout.strip() or "(изменений нет)"`)."""
    return {len(diff_text.encode("utf-8")),
           len(diff_text.strip().encode("utf-8"))}


def _numbers_in(text: str) -> set:
    return {int(n) for n in re.findall(r"\d+", text)}


def _call_capturing_stdout(fn, *args):
    """(результат, напечатанное) — `tests.sandbox.capture` отбрасывает
    возврат функции, а здесь нужны оба: булев вердикт гейта и текст,
    который он печатает (AC-3 требует цифры и в печати тоже)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args)
    return result, buf.getvalue()


class _CapacityGateSandbox(GitFeatureBranchSandbox):

    def setUp(self):
        super().setUp()
        self.t = {"title": "Тест гейта ёмкости — исключение tasks/<id>",
                  "branch": self.BRANCH}

    def refuses(self) -> bool:
        return fsm_advance._capacity_gate_refuses(
            self.conn, self.TASK, self.t, "in_dev")

    def refuses_with_output(self):
        return _call_capturing_stdout(
            fsm_advance._capacity_gate_refuses,
            self.conn, self.TASK, self.t, "in_dev")


class Ac1TasksDirNeverCountsTowardTheMeasureTest(_CapacityGateSandbox):
    """Диф `tasks/<id>/` растёт от отсутствия до величины, В РАЗЫ большей
    потолка гейта, пока код не менялся вовсе, кроме небольшой начальной
    правки, — вердикт перехода не имеет права качнуться, потому что мера
    считает diff БЕЗ `tasks/<id>/` (AC-1): её рост там попросту не виден,
    а не «пока укладывается в запас».

    Ловит мутацию: исключение реализовано лишь частично — скажем, только
    для `tasks/<id>/SPEC.md`/`PLAN.md`, но не для `acceptance_tests/`,
    где по конвенции живёт планка (skills/test-authoring.md). Тест кладёт
    большой файл именно в `acceptance_tests/`, поэтому частичное
    исключение ловится тем же способом, что и полное отсутствие
    исключения.
    """

    def test_ac1_growing_the_tasks_dir_diff_does_not_flip_the_verdict(self):
        self.write(self.CODE_FILE, "базовый код\n" + "x" * 2000 + "\n")
        self.commit("код: малая правка")
        self.assertFalse(
            self.refuses(),
            "малая правка кода одна не имеет права отказывать переходу")

        self.write(f"tasks/{self.TASK}/acceptance_tests/test_stub.py",
                  "y" * (CAP * 3) + "\n")
        self.commit("артефакты: планка (в разы больше потолка гейта)")

        self.assertFalse(
            self.refuses(),
            "diff `tasks/<id>/`, в разы крупнее потолка гейта, не имеет "
            "права менять вердикт — мера обязана его не считать (AC-1)")


class Ac4CombinedOverCapButCodeAloneUnderPassesTest(_CapacityGateSandbox):
    """Код ниже потолка сам по себе, а НЕисключённая сумма (код + планка)
    выше потолка — переход не отклонён (буквальная формулировка AC-4).

    Ловит мутацию: гейт продолжает мерить diff целиком (без исключения
    `tasks/<id>/`) — сумма выше потолка отказала бы переходу, хотя код
    сам по себе укладывается с запасом."""

    def test_ac4_tasks_dir_pushing_the_raw_sum_over_the_cap_does_not_refuse(self):
        self.write(self.CODE_FILE, "базовый код\n" + "x" * 2000 + "\n")
        self.commit("код: небольшая правка")
        self.write(f"tasks/{self.TASK}/acceptance_tests/test_stub.py",
                  "y" * CAP + "\n")
        self.commit("артефакты: планка")

        raw_diff = self.git("diff", f"{config.MAIN_BRANCH}...{self.BRANCH}")
        self.assertGreater(
            len(raw_diff.encode("utf-8")), CAP,
            "сценарий сконструирован неверно: НЕисключённая сумма обязана "
            "превышать потолок, иначе сценарий AC-4 не воспроизведён")

        self.assertFalse(
            self.refuses(),
            "код ниже потолка сам по себе — переход не имеет права "
            "отклоняться только из-за большой планки в tasks/<id>/ (AC-4)")


class Ac5CodeAloneOverCapStillRefusesTest(_CapacityGateSandbox):
    """Код сам по себе крупнее потолка — переход отклонён, поведение не
    регрессирует относительно AC-12 tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X.

    Ловит мутацию: исключение `tasks/<id>/` по ошибке реализовано как
    общий сдвиг/скидка потолка (например, потолок увеличен на типичный
    размер планки вместо вычитания её байт из diff) — код, который сам по
    себе обязан отказывать, тогда прошёл бы гейт."""

    def test_ac5_code_diff_alone_above_the_cap_still_refuses(self):
        self.write(self.CODE_FILE, "базовый код\n" + "x" * (CAP + 50_000) + "\n")
        self.commit("код: правка крупнее потолка сама по себе")

        self.assertTrue(
            self.refuses(),
            "diff кода, сам по себе крупнее потолка, обязан отклонять "
            "переход — тем же способом, что и до этой задачи (AC-5)")


class Ac3RefusalNamesBothNumbersTest(_CapacityGateSandbox):
    """Отказ гейта (журнал И печать) называет обе цифры дословно:
    фактический размер diff кода (без `tasks/<id>/`) и размер diff,
    приходящегося на `tasks/<id>/` (исключённые артефакты) — иначе
    Оператор на мосту не видит, что именно из двух раздуло снимок.

    Ловит мутацию: отказ по-прежнему называет только одну (объединённую
    или только кодовую) цифру — тест не находит вторую (размер
    артефактов) ни в журнале, ни в печати."""

    def test_ac3_refusal_names_the_code_size_and_the_excluded_artifacts_size(self):
        self.write(self.CODE_FILE,
                  "базовый код\n" + "x" * (CAP + 50_000) + "\n")
        self.commit("код: правка крупнее потолка сама по себе")
        self.write(f"tasks/{self.TASK}/acceptance_tests/test_stub.py",
                  "y" * 300 + "\n")
        self.commit("артефакты: маленькая планка")

        # Независимый оракул — те же самые пути, разделённые pathspec'ом
        # git (магия `:!` = `:(exclude)`), которую и предлагает SPEC:
        # какой бы приём исключения ни выбрала реализация, итоговое
        # разбиение diff'а на «код» и «tasks/<id>/» им же и определено.
        # `_plausible_byte_counts` берёт байты и «как есть», и после
        # `.strip()` — та же нормализация хвостового перевода строки, что
        # уже делает `review.git_diff_part` для существующей (кодовой)
        # цифры; SPEC не фиксирует, обязана ли новая (artefacts) цифра
        # считаться тем же приёмом, так что тест принимает оба варианта,
        # не привязываясь к побайтовому совпадению одной лишней \n.
        code_diff = self.git(
            "diff", f"{config.MAIN_BRANCH}...{self.BRANCH}",
            "--", ".", f":!tasks/{self.TASK}/")
        tasks_diff = self.git(
            "diff", f"{config.MAIN_BRANCH}...{self.BRANCH}",
            "--", f"tasks/{self.TASK}/")
        code_sizes = _plausible_byte_counts(code_diff)
        tasks_sizes = _plausible_byte_counts(tasks_diff)
        self.assertGreater(min(code_sizes), CAP, "сценарий: код сам по "
                           "себе обязан превышать потолок (иначе гейт не "
                           "откажет)")
        self.assertGreater(min(tasks_sizes), 0, "сценарий: артефакты "
                           "обязаны нести ненулевой diff, иначе вторую "
                           "цифру нечем отличить от нуля")

        refused, printed = self.refuses_with_output()

        self.assertTrue(refused)
        details = self.journal_details()
        journal_text = "\n".join(details)
        journal_numbers = _numbers_in(journal_text)
        printed_numbers = _numbers_in(printed)
        self.assertTrue(
            journal_numbers & code_sizes,
            f"журнал обязан назвать размер diff кода (один из "
            f"{code_sizes}): {details}")
        self.assertTrue(
            journal_numbers & tasks_sizes,
            f"журнал обязан назвать размер исключённых артефактов (один "
            f"из {tasks_sizes}): {details}")
        self.assertTrue(
            printed_numbers & code_sizes,
            f"печать обязана назвать размер diff кода (один из "
            f"{code_sizes}): {printed!r}")
        self.assertTrue(
            printed_numbers & tasks_sizes,
            f"печать обязана назвать размер исключённых артефактов (один "
            f"из {tasks_sizes}): {printed!r}")


if __name__ == "__main__":
    unittest.main()
