"""AC-5/AC-7 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): гейт применимости
приложений на выходе `in_dev` — неприменимое приложение отказывает
переходу именованной записью журнала, применимое и отсутствующее
пропускают переход как сегодня.

Красен до реализации: гейта применимости в списке гейтов `in_dev` ещё нет, поэтому задача с неприменимым приложением уходит в `verifying`, а записи «переход отклонён: приложение PLAN неприменимо» в журнале нет ни одной (`test_ac5_*`). Оба теста AC-7 — сохранение сегодняшнего поведения, они зелёные с рождения и краснеют, если новый гейт отказывает лишнему.

Наблюдается исход настоящего `fsm.cmd_advance`, а не вызов гейта по
имени: SPEC имени нового гейта не называет, а место в списке гейтов
`in_dev` на наблюдаемый исход влиять не вправе (`_sandbox.py`,
докстринг модуля).

Провалидировано стабом (решение Оператора 03.09): временный гейт поверх
`fsm_advance.in_dev` (разбор приложений с артефактной ветки, `git apply
--check` в worktree базы сравнения, журнал именованным действием)
зеленит все три теста файла; стаб удалён, репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402
import _sandbox  # noqa: E402

# Опорные слова ответа `git apply --check` на неприменимый хунк («error:
# patch failed: <путь>») — и в переводе, на случай локализованного git в
# среде прогона: сверяется НАЛИЧИЕ ответа git в detail, а не его
# дословная формулировка (её задаёт git, не реализация).
GIT_ANSWER_WORDS = ("patch", "error", "apply", "ошибк", "заплат")


class InDevApplicabilityGateTest(_sandbox.InDevAppendixSandbox):

    def test_ac5_inapplicable_appendix_refuses_the_transition(self):
        """PLAN с приложением, чей хунк не совпадает ни с одной строкой
        файла базы сравнения (`git apply --check` отказывает): переход
        отклонён — задача осталась в `in_dev`, в журнале запись с
        действием «переход отклонён: приложение PLAN неприменимо», её
        detail несёт путь приложения и текст ответа git.

        Ловит мутацию: гейт зовёт `git apply` без `--check` (или
        игнорирует код возврата) — неприменимое приложение проехало бы
        гейт молча, задача ушла бы в `verifying`, и проверка состояния
        ниже покраснеет; та же проверка ловит и гейт, вовсе не
        подключённый к списку `in_dev`. Проверка detail ловит вторую
        мутацию: отказ журналируется без пути/ответа git, и роль в брифе
        читает «неприменимо» без единой подсказки, ЧТО неприменимо.
        """
        self.commit_plan([_parse.appendix_section(
            [_sandbox.stale_diff_block(_parse.PROTECTED_FILE,
                                       "правка Оператора")],
            suffix=f": устаревший хунк {_parse.PROTECTED_FILE}")])

        out = self.advance()

        self.assertEqual(
            self.state(), "in_dev",
            f"неприменимое приложение обязано отказать переходу; вывод "
            f"advance: {out!r}")
        matching = [detail for action, detail in self.refusals()
                    if action == _sandbox.INAPPLICABLE_REFUSAL_ACTION]
        self.assertTrue(
            matching,
            f"нет записи журнала «{_sandbox.INAPPLICABLE_REFUSAL_ACTION}»; "
            f"журнал задачи:\n{self.journal_blob()}\nвывод advance: {out!r}")
        detail = matching[-1]
        self.assertIn(_parse.PROTECTED_FILE, detail,
                      f"detail отказа не называет путь приложения: {detail!r}")
        self.assertTrue(
            any(word in detail.lower() for word in GIT_ANSWER_WORDS),
            f"detail отказа не несёт текста ответа git: {detail!r}")

    def test_ac7_applicable_appendix_passes_the_gate(self):
        """PLAN с приложением, порождённым настоящим `git diff` по файлу
        базы сравнения: гейт пропускает — задача уходит из `in_dev`
        (`verifying`, ADR-0015), записи об отказе приложения нет.

        Ловит мутацию: гейт отказывает на ЛЮБОМ найденном приложении
        (условие применимости перепутано местами — `returncode == 0`
        вместо `!= 0`) — задача осталась бы в `in_dev`, и ни одно
        приложение никогда не доехало бы до мержа.
        """
        self.commit_plan([_parse.appendix_section(
            [self.applicable_diff_block(_parse.PROTECTED_FILE,
                                        "вторая строка Оператора")],
            suffix=f": применимая правка {_parse.PROTECTED_FILE}")])

        out = self.advance()

        self.assertEqual(
            self.state(), "verifying",
            f"применимое приложение не имеет права держать задачу в "
            f"in_dev; журнал:\n{self.journal_blob()}\nвывод: {out!r}")
        self.assertEqual(
            [a for a, _d in self.refusals()
             if a == _sandbox.INAPPLICABLE_REFUSAL_ACTION], [])

    def test_ac7_plan_without_appendices_advances_as_before(self):
        """PLAN без разделов «## Приложение» проходит выход из `in_dev` в
        точности как до задачи: задача в `verifying`, ни одной записи
        «переход отклонён …» в журнале.

        Ловит мутацию: гейт считает пустой список приложений отказом
        (fail-closed «приложений нет — проверять нечего, значит не
        пройдено») либо падает на PLAN без раздела — всякая задача
        артели, не предлагающая приложений, застряла бы в `in_dev`.
        """
        self.commit_plan()

        out = self.advance()

        self.assertEqual(self.state(), "verifying",
                         f"журнал:\n{self.journal_blob()}\nвывод: {out!r}")
        self.assertEqual(self.refusals(), [])


if __name__ == "__main__":
    unittest.main()
