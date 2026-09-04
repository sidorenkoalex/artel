"""AC-2 (tasks/01M1NBWRTAHSX9FQGTQWENY80A/SPEC.md): «Каждый включённый в
пакет компонент ANSWER-n.md даёт в журнале задачи запись с
sha256-фингерпринтом его содержимого (той же формы, что журнальная
запись «бриф: компонент» для компонентов брифа developer/analyst/
test_author в orchestrator/brief.py).»

«Той же формы» — образец `orchestrator/brief.py::_journal_component`:
`store.journal(conn, task_id, role, "бриф: компонент", f"{label}:
sha256={component_hash(text)}")`, где `component_hash` делегирует
`context_package.sha256_of` (docstring `brief.component_hash`). Тест
сверяет ИМЕННО эту форму — action «бриф: компонент», detail
«<путь>: sha256=<hex>» с хэшем, посчитанным той же функцией.

Красен до реализации: `action="бриф: компонент"` в журнале шага ревьювера
СЕГОДНЯ уже встречается — но только от скилов роли (`brief.skills_text`,
`orchestrator/runner.py`, три записи на КАЖДЫЙ запуск ЛЮБОЙ роли,
включая ревьювера: conventions-core/escalation-rules/review-checklist).
`review.review_package` же не пишет в журнал ничего вовсе (единственная
относящаяся к пакету запись — сводная «ревью-пакет собран»,
`orchestrator/runner.py:254`, суммарный размер, не по компонентам) — до
того, как ANSWER-n.md вообще существует у задачи, запросу «есть ли среди
записей «бриф: компонент» такая, что упоминает tasks/<TASK>/ANSWER-1.md»
неоткуда взяться. Тест фильтрует записи по этому пути, а не проверяет
список целиком пустым — иначе он бы падал уже на записях скилов, не
имеющих отношения к этому критерию.

Стаб корректной реализации (`context_package.sha256_of`,
`store.journal(conn, task_id, "reviewer", "бриф: компонент", ...)`
вызванный из `review.review_package` по каждому найденному ANSWER-n.md)
прогонялся вручную при написании этого теста — зеленеет; в репозиторий
не коммитится (текущая реализация `orchestrator/review.py` не содержит
такого вызова).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import context_package  # noqa: E402
from _sandbox import AnswerInReviewPackageSandbox  # noqa: E402

ANSWER_1 = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: батч AC-2

## Ответы

Вопрос 1 — вариант A: маркер-содержимого-ac2-9d41.
"""


class Ac2AnswerComponentJournaledTest(AnswerInReviewPackageSandbox):

    def test_ac2_answer_component_journal_entry_carries_sha256_of_its_content(self):
        """Один ANSWER-1.md у задачи — запуск шага ревьювера обязан
        оставить в журнале запись `action="бриф: компонент"` с деталью
        вида «tasks/<TASK>/ANSWER-1.md: sha256=<хэш содержимого файла>».

        Ловит мутацию: реализация включает ANSWER-n.md в текст пакета
        (закрывает AC-1), но не вызывает `store.journal` для него вовсе
        (пропущенный шаг журналирования) — среди записей `action="бриф:
        компонент"` (там уже есть три записи про скилы роли, см. докстринг
        модуля) не найдётся ни одной про путь ANSWER-1.md, и `assertTrue
        (matching)` покраснеет; либо реализация журналирует с хэшем
        ОБЁРНУТОГО текста (после `brief.wrap_boundary`) вместо исходного —
        вычисленный здесь `sha256_of(answer_text)` (по исходному тексту)
        не совпадёт ни с одной записью.
        """
        answer_text = ANSWER_1.format(task=self.TASK)
        self.add_answer(1, answer_text)
        expected_sha = context_package.sha256_of(answer_text)

        self.run_agent("review")

        entries = self.journal_details("бриф: компонент")
        matching = [d for d in entries
                   if f"tasks/{self.TASK}/ANSWER-1.md" in d]
        self.assertTrue(
            matching, f"нет записи журнала про tasks/{self.TASK}/"
            f"ANSWER-1.md среди: {entries}")
        self.assertIn(
            f"sha256={expected_sha}", matching[0],
            "sha256 в журнале не совпадает с sha256 исходного содержимого "
            "ANSWER-1.md")

    def test_ac2_two_answer_files_each_get_their_own_journal_entry(self):
        """Два ANSWER-файла — две отдельные журнальные записи, каждая со
        своим sha256 (не одна общая запись на оба).

        Ловит мутацию: реализация журналирует один сводный хэш по
        конкатенации всех ANSWER-компонентов вместо отдельной записи на
        каждый — тест не найдёт записи с sha256 ВТОРОГО файла, посчитанным
        по ЕГО СОБСТВЕННОМУ содержимому.
        """
        answer_1 = ANSWER_1.format(task=self.TASK)
        answer_2 = answer_1.replace("ac2-9d41", "ac2-second-b207")
        self.add_answer(1, answer_1)
        self.add_answer(2, answer_2)
        sha_1 = context_package.sha256_of(answer_1)
        sha_2 = context_package.sha256_of(answer_2)

        self.run_agent("review")

        entries = self.journal_details("бриф: компонент")
        self.assertTrue(any(
            f"tasks/{self.TASK}/ANSWER-1.md" in d and f"sha256={sha_1}" in d
            for d in entries), f"запись про ANSWER-1.md не найдена: {entries}")
        self.assertTrue(any(
            f"tasks/{self.TASK}/ANSWER-2.md" in d and f"sha256={sha_2}" in d
            for d in entries), f"запись про ANSWER-2.md не найдена: {entries}")


if __name__ == "__main__":
    import unittest
    unittest.main()
