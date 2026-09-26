"""AC-10 и AC-11 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): канареечная
задача и задача внешнего target проходят переход без проверки гейта даже
при находке в диффе; молчание git на базе сравнения, на списке файлов
диффа или на чтении содержимого существующего в head пути — отказ
(fail-closed), а не молчаливый пропуск.

Красен до реализации: обёртки `_test_integrity_gate_refuses` в
`orchestrator/fsm_advance.py` (требование 6) ещё нет — вызов падает
`AttributeError` на каждом сценарии.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (ALPHA_WITHOUT_SECOND_METHOD, REFUSAL_ACTION,  # noqa: E402
                      TestIntegritySandbox)
from orchestrator import gitcmd  # noqa: E402


class _DeletedFileSandbox(TestIntegritySandbox):
    """Дифф с заведомой находкой (удалён `tests/test_doomed.py`) — общая
    завязка обоих классов ниже: и пропуски AC-10, и сбои git AC-11
    проверяются на диффе, который сам по себе обязан отказывать."""

    def setUp(self):
        super().setUp()
        self.remove("tests/test_doomed.py")
        self.commit()


class GateSkipConditionsTest(_DeletedFileSandbox):

    def test_ac10_canary_task_skips_the_gate(self):
        """Канареечная задача (`is_canary`) проходит переход, хотя дифф
        несёт удалённый файл тестов; гейт не идёт даже за базой сравнения.

        Ловит мутацию: условие `t["is_canary"]` не перенесено из образца
        (`_mutation_claim_gate`) либо стоит ПОСЛЕ чтения git — канарейка
        (одноразовая задача пула, чей `verifying` убивает её сразу по
        входу) начинает упираться в рубеж, которому в её маршруте нечего
        защищать.
        """
        self.set_task_fields(is_canary=1)

        def boom(*args, **kwargs):
            raise AssertionError("гейт неослабления тестов не обязан звать "
                                 "diff_base для канареечной задачи")

        with mock.patch.object(gitcmd, "diff_base", boom):
            outcome = self.run_gate()

        self.assertFalse(outcome.refused,
                         f"канарейка проходит без проверки (AC-10); "
                         f"журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)

    def test_ac10_external_target_task_skips_the_gate(self):
        """Задача внешнего target (`target != config.DEFAULT_TARGET`)
        проходит переход по той же причине: дифф в `config.ROOT` не видит
        код внешнего target.

        Ловит мутацию: условие внешнего target потеряно — гейт считает
        дифф ПУЛЬТА кодом чужого репозитория и отказывает задаче
        внешнего target за находки, к которым она не имеет отношения.
        """
        self.set_task_fields(target="some-external-target")

        def boom(*args, **kwargs):
            raise AssertionError("гейт неослабления тестов не обязан звать "
                                 "diff_base для внешнего target")

        with mock.patch.object(gitcmd, "diff_base", boom):
            outcome = self.run_gate()

        self.assertFalse(outcome.refused,
                         f"внешний target проходит без проверки (AC-10); "
                         f"журнал: {outcome.journal}")
        self.assertNotIn(REFUSAL_ACTION, outcome.actions, outcome.journal)


class GitFailureFailsClosedTest(_DeletedFileSandbox):
    """Молчание git изображается отказом САМОЙ git-команды (подмена
    `gitcmd.git` фильтром), а не мока конкретного примитива чтения: имя
    примитива, которым реализация возьмёт список файлов диффа, требование
    3 оставляет за ней (новый `git diff -M --name-status` рядом с
    существующим `gitcmd.diff_names`) — планка не вправе пинать выбор,
    но вправе требовать отказа, когда git не отвечает НИ НА ОДИН из них.
    """

    def setUp(self):
        super().setUp()
        # Помимо удалённого файла дифф несёт ИЗМЕНЁННЫЙ, существующий в
        # дереве head, — без него у сценария «git не ответил на чтение
        # содержимого» нет предмета (у удалённого пути содержимого в head
        # нет и законно).
        self.write("tests/test_alpha.py", ALPHA_WITHOUT_SECOND_METHOD)
        self.commit()

    def _failing_git(self, *subcommands: str):
        """Подмена `gitcmd.git`: перечисленные подкоманды отвечают как
        сломанный git, остальные исполняются по-настоящему."""
        real_git = gitcmd.git

        def fake(*args: str):
            if args and args[0] in subcommands:
                return subprocess.CompletedProcess(
                    args, 128, "", "fatal: bad object (тест)")
            return real_git(*args)

        return mock.patch.object(gitcmd, "git", fake)

    def _assert_named_refusal_about_git(self, outcome):
        self.assertTrue(outcome.refused,
                        f"сбой git обязан отказывать, а не пропускать "
                        f"(AC-11); журнал: {outcome.journal}")
        self.assertIn(REFUSAL_ACTION, outcome.actions, outcome.journal)
        self.assertIn("git", outcome.detail,
                      f"detail обязан объяснить, что не ответил git "
                      f"(AC-11); detail: {outcome.detail}")
        self.assertIn("advance", outcome.printed,
                      f"подсказка обязана назвать повтор advance (AC-11); "
                      f"stdout: {outcome.printed}")

    def test_ac11_silent_diff_base_refuses(self):
        """git не ответил на определение базы сравнения — отказ с
        именованным действием, деталью о сбое git и подсказкой повторить
        advance.

        Ловит мутацию: `base is None` трактуется как «сравнивать не с
        чем» и гейт возвращает `None` (fail-open, как у соседа по гейту
        мержа) — на переходе это значит, что сломанный git ОТКРЫВАЕТ
        рубеж целиком, вопреки ADR-0002.
        """
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            outcome = self.run_gate()
        self._assert_named_refusal_about_git(outcome)

    def test_ac11_silent_diff_listing_refuses(self):
        """Тот же класс отказа для второй git-точки — списка файлов
        диффа: ни один вид `git diff` не отвечает, база при этом
        определена.

        Ловит мутацию: fail-closed поставлен только на `diff_base`
        (точечный фикс одной из двух точек сбоя), а пустой/`None` ответ
        на список файлов уходит дальше как «находок нет» — рубеж молча
        открывается ровно на сломанном git.
        """
        with self._failing_git("diff"):
            outcome = self.run_gate()
        self._assert_named_refusal_about_git(outcome)

    def test_ac11_silent_show_on_path_present_in_head_refuses(self):
        """git не ответил на чтение содержимого пути, который РЕАЛЬНО
        есть в дереве head (`git ls-tree` отвечает как обычно): отказ, а
        не трактовка «файла нет, значит нечего сравнивать».

        Ловит мутацию: `gitcmd.show`, вернувший `None`, всюду читается
        как «пути в этой ветке нет» — сбой чтения существующего файла
        неотличим от легитимного удаления, и ослабление внутри такого
        файла проходит рубеж (тот же дефект, что закрывала итерация 3
        ревью гейта заявки мутации, `test_unclassified_show_failure_on_
        path_present_in_tree_refuses`).
        """
        with self._failing_git("show"):
            outcome = self.run_gate()
        self._assert_named_refusal_about_git(outcome)


if __name__ == "__main__":
    unittest.main()
