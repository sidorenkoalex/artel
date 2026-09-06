"""AC-3 / AC-9 задачи 01M1TKP08PKB87K8772H69GCXJ.

AC-3: тексты записей журнала (`store.journal`) и эскалаций
(`store.set_state(..., "escalated", ...)`) остаются байт-в-байт такими
же, как до рефакторинга — здесь три сценария, явно названных
критерием: именованный отказ «планка не найдена в источнике», инцидент
«would be overwritten by merge», красные приёмочные тесты после
подтяжки.

AC-9: смоук по трём сценариям (свежая ветка; конфликт merge только по
`docs/codebase-map.md`, авторазрешаемый; конфликт merge по двум файлам,
неразрешаемый) — журнал и stdout совпадают с зафиксированной здесь
фикстурой байт-в-байт.

Зелёный с рождения: все шесть сценариев собраны и провалидированы
ПРОТИВ сегодняшнего, ещё не тронутого этой задачей
`fsm._pull_main_or_escalate` — тексты literal-строк ниже списаны прямо
с его текущего исходного кода (`orchestrator/fsm.py:240-457`), задача
обязана сохранить их байт-в-байт (правило фазы R, требование 4/6), не
изменить.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import MAP_REL, PullNodeSandbox  # noqa: E402
from orchestrator import acceptance, artifact_branch, config, fsm, gitcmd  # noqa: E402
from tests.sandbox import capture_new_task_id  # noqa: E402

OVERWRITE_STDERR = (
    "error: Your local changes to the following files would be "
    "overwritten by merge:\n\tsome.txt\nPlease commit your changes or "
    "stash them before you merge.\nAborting")


class Ac9SmokeFixtureTest(PullNodeSandbox):

    def test_ac9_fresh_scenario_matches_recorded_fixture(self):
        """Ветка не отстала — журнал пуст, stdout пуст, возврат `"fresh"`.

        Ловит мутацию: делегация `pull.py` заводит побочный журнал даже
        на «ветка не отстала» (например, лишняя диагностическая запись)
        — `assertEqual(self.journal_details(), [])` это поймает.
        """
        with mock.patch.object(gitcmd, "commits_behind", return_value=0):
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        self.assertEqual(outcome, "fresh")
        self.assertEqual(self.journal_details(), [])
        self.assertEqual(out, "")

    def test_ac9_map_only_conflict_autoresolved_matches_recorded_fixture(self):
        """Конфликт merge только по `docs/codebase-map.md` — авторазрешён
        регенерацией; журнал несёт РОВНО одну запись с зафиксированным
        текстом, stdout пуст, возврат `"pulled"`.

        Ловит мутацию: текст записи авторазрешения теряет упоминание
        способа разрешения (`checkout --theirs`/регенератора) или файла
        карты — `assertEqual` по полному тексту (не `assertIn`) это
        поймает, в отличие от `tests/test_fsm_map_conflict_autoresolve.py`
        (тот проверяет только вхождение подстроки).
        """
        self.write_acceptance_plank()
        side_effect = self.in_repo_side_effect(conflict_files=[MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        expected_detail = (
            f"{MAP_REL} — единственный конфликтующий файл, разрешён "
            f"checkout --theirs + регенерация scripts/codebase_map.py на "
            f"слитом дереве worktree задачи")

        self.assertEqual(outcome, "pulled")
        self.assertEqual(self.journal_details(), [expected_detail])
        self.assertEqual(out, "")

    def test_ac9_two_file_conflict_unresolved_matches_recorded_fixture(self):
        """Конфликт merge по двум файлам (карта + `shared.txt`) — не
        авторазрешается; журнал несёт запись эскалации с зафиксированным
        текстом, stdout — печать перехода `store.set_state` с тем же
        текстом, возврат `"escalated"`.

        Ловит мутацию: текст эскалации теряет список конфликтных файлов
        или хвост stderr `git merge` — `assertIn`/`assertEqual` по
        полному тексту это поймают.
        """
        side_effect = self.in_repo_side_effect(
            conflict_files=[MAP_REL, "shared.txt"],
            merge_stderr="CONFLICT (content): Merge conflict in "
            "docs/codebase-map.md")
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        note = ("конфликтные файлы: docs/codebase-map.md, shared.txt; "
               "CONFLICT (content): Merge conflict in docs/codebase-map.md")
        expected_detail = (
            f"конфликт подтяжки {config.MAIN_BRANCH} в ветку "
            f"{self.BRANCH}: {note}")

        self.assertEqual(outcome, "escalated")
        # `assertIn`, не `assertEqual` по всему списку: `store.set_state`
        # на "escalated" безусловно заводит ещё и свою запись «sha
        # зафиксирован» (`store.record_fixation`, хук на КАЖДОМ переходе,
        # `orchestrator/store.py`) — она не относится к предмету AC-3/AC-9
        # (текст подтяжки), просто соседствует с ним в том же журнале.
        self.assertIn(expected_detail, self.journal_details())
        # stdout этой строки — печать самого `store.set_state`
        # (`orchestrator/store.py`: `print(f"[{task_id}] -> {state}
        # ({detail})")`), не собственная печать `_pull_main_or_escalate`
        # (та молчит на этой ветке) — фиксируем и её байт-в-байт (AC-9).
        self.assertEqual(out.rstrip("\n"),
                         f"[{self.TASK}] -> escalated  ({expected_detail})")
        acc_run.assert_not_called()


class Ac3MessageTextTest(PullNodeSandbox):

    def test_ac3_named_refusal_plank_not_found_exact_text(self):
        """SPEC несёт AC-разметку, но артефактная ветка не несёт
        `acceptance_tests/` — журнал и stdout несут ИМЕННО текст
        «переход отклонён: планка не найдена в источнике» с полным
        зафиксированным пояснением, не сокращённый/перефразированный
        вариант.

        Ловит мутацию: пояснение отказа теряет имя артефактной ветки или
        путь `tasks/<id>/acceptance_tests/` — `assertEqual` по полному
        тексту это поймает.
        """
        self.write_spec_requiring_ac_without_plank()
        side_effect = self.in_repo_side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        artifact_branch_name = artifact_branch.branch_name(self.TASK)
        expected_detail = (
            f"планка не найдена в источнике: артефактная ветка "
            f"{artifact_branch_name} не несёт tasks/{self.TASK}/"
            f"acceptance_tests/, а tests_writing не пропущена "
            f"легитимно (skip_tests не задан в SPEC)")
        expected_stdout = f"[{self.TASK}] переход отклонён: {expected_detail}"

        self.assertEqual(outcome, "refused")
        self.assertEqual(self.journal_details(), [expected_detail])
        self.assertEqual(out.rstrip("\n"), expected_stdout)
        acc_run.assert_not_called()

    def test_ac3_incident_would_be_overwritten_exact_text(self):
        """`git merge` отказывает с «would be overwritten by merge» ДО
        начала слияния (очистка worktree не устранила отказ) — это
        инцидент, не спор версий: эскалация без слова «конфликт», с
        зафиксированным текстом.

        Ловит мутацию: инцидент этого класса склеен с обычной веткой
        «конфликт подтяжки» (получает её текст/слово «конфликт») —
        `assertEqual`/`assertNotIn` по формулировке это поймает.
        """
        side_effect = self.in_repo_side_effect(overwrite_stderr=OVERWRITE_STDERR)
        with mock.patch.object(gitcmd, "commits_behind", return_value=6), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        expected_detail = (
            f"подтяжка {config.MAIN_BRANCH} в ветку {self.BRANCH} отказала "
            f"после попытки очистки worktree — {OVERWRITE_STDERR}")

        self.assertEqual(outcome, "escalated")
        self.assertIn(expected_detail, self.journal_details())
        self.assertNotIn("конфликт подтяжки", expected_detail)
        self.assertEqual(self.abort_calls, [],
                         "инцидент до начала слияния не абортит merge — "
                         "абортить нечего")
        self.assertEqual(out.rstrip("\n"),
                         f"[{self.TASK}] -> escalated  ({expected_detail})")
        acc_run.assert_not_called()

    def test_ac3_red_acceptance_after_pull_exact_text(self):
        """Merge проходит чисто, но приёмочные тесты планки красные —
        эскалация с полным хвостом прогона, слияние НЕ откатывается.

        Ловит мутацию: текст эскалации теряет хвост прогона (`tail`) или
        неверно утверждает, что слияние откатывается, — `assertEqual` по
        тексту и `assertEqual(self.abort_calls, [])` это поймают.
        """
        self.write_acceptance_plank()
        side_effect = self.in_repo_side_effect()
        tail = "ПРИЁМОЧНЫЙ-МАРКЕР-КРАСНЫЙ"
        with mock.patch.object(gitcmd, "commits_behind", return_value=7), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(False, tail)):
            out, outcome = capture_new_task_id(self.pull, "in_dev")

        expected_detail = (
            f"приёмочные тесты красные после подтяжки {config.MAIN_BRANCH} "
            f"(слияние сохранено, откат не выполняется):\n{tail}")

        self.assertEqual(outcome, "escalated")
        self.assertIn(expected_detail, self.journal_details())
        self.assertEqual(self.abort_calls, [])
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(out.rstrip("\n"),
                         f"[{self.TASK}] -> escalated  ({expected_detail})")


if __name__ == "__main__":
    unittest.main()
