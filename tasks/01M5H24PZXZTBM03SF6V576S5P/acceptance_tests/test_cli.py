"""Разбор флага `--parallel`, справка, отказ набора с Codex и сверка формы `--sha` в `canary run-task`.

Группа: разовый
Красен до реализации: флага --parallel и сверки формы --sha в run-task ещё нет — справка его не называет, повтор флага и набор с Codex не отказывают, короткий --sha доходит до ведения.

Файл держит приёмку задачи через закрытые швы `canary`/`artel` (подмена
`_set_plan`, `_run_one_task`, `_detach_canary`) — правила долгоживущих файлов
их запрещают, поэтому группа разовая; долгоживущую проверку свойства несут
тесты разработчика по требованию 9 SPEC.
"""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import (CanaryParallelSandbox, FULL_SHA, SET_NAME,  # noqa: E402
                      SHORT_SHA, SUMMARY)
from orchestrator import artel, canary, config, store  # noqa: E402

OLD_KWARGS = {"k", "sha", "set_name", "templates"}


class HelpAndArgvTest(CanaryParallelSandbox):
    def test_ac2_help_line_names_parallel_and_old_call_without_new_kwarg(self):
        """Справка и вызов `cmd_canary` без флага и с флагом.

        Строка справки `artel.py` с `canary --k` и `--template` называет
        `--parallel`. Без флага `_cmd_canary` зовёт `cmd_canary` ровно прежними
        именованными аргументами; с флагом — передаёт сверх них новый.

        Ловит мутацию: новый параметр передаётся всегда (`parallel=False` без
        флага) — набор именованных аргументов вызова без флага шире прежнего;
        либо флаг не дописан в строку справки.
        """
        lines = [line for line in (artel.__doc__ or "").splitlines()
                 if "canary --k" in line and "--template" in line]
        self.assertTrue(lines, "в справке нет строки canary --k … --template …")
        self.assertTrue(any("--parallel" in line for line in lines), lines)
        argv = ["--k", "2", "--sha", SHORT_SHA, "--set", SET_NAME,
                "--template", "alfa,beta"]
        with mock.patch.object(canary, "cmd_canary") as call:
            artel._cmd_canary(list(argv))
        self.assertEqual(set(call.call_args.kwargs), OLD_KWARGS)
        self.assertEqual(call.call_args.args, ())
        with mock.patch.object(canary, "cmd_canary") as call:
            artel._cmd_canary(argv + ["--parallel"])
        self.assertTrue(OLD_KWARGS < set(call.call_args.kwargs),
                        call.call_args.kwargs)


class ParallelFlagTest(CanaryParallelSandbox):
    def test_ac3_repeated_parallel_refused_before_detach_branch(self):
        """Повторный `--parallel` — отказ «canary: повторный --parallel».

        Отказ и с `--detach` в argv: ни отвязанный процесс, ни `cmd_canary` не
        запускаются.

        Ловит мутацию: проверка повтора стоит после ветки `--detach` — с
        `--detach` повтор уходит в отвязанный процесс без отказа.
        """
        for extra in ([], ["--detach"]):
            with self.subTest(extra=extra), \
                    mock.patch.object(artel, "_detach_canary") as detach, \
                    mock.patch.object(canary, "cmd_canary") as call:
                with self.assertRaises(SystemExit) as caught:
                    artel._cmd_canary(["--k", "2", "--parallel", "--parallel",
                                       *extra])
                self.assertIn("canary: повторный --parallel",
                              str(caught.exception.code))
                detach.assert_not_called()
                call.assert_not_called()

    def test_ac3_parallel_with_detach_reaches_detached_process(self):
        """`--parallel --detach` — отвязанный процесс получает `--parallel`.

        argv отвязанного процесса несёт `--parallel` ровно один раз и ровно
        один `--result-file`; `--detach` в него не уходит.

        Ловит мутацию: `--parallel` снимается из argv до `_detach_canary` либо
        дочерний прогон получает второй файл результата.
        """
        seen = []

        def popen(argv, *args, **kwargs):
            seen.append([str(a) for a in argv])
            return mock.Mock(pid=4242)

        with mock.patch.object(artel.subprocess, "Popen", popen):
            out = self.capture(artel._cmd_canary,
                               ["--k", "2", "--parallel", "--detach"])
        self.assertEqual(len(seen), 1, out)
        argv = seen[0]
        self.assertEqual(argv.count("--parallel"), 1, argv)
        self.assertEqual(argv.count("--result-file"), 1, argv)
        self.assertNotIn("--detach", argv)
        self.assertEqual(out.count("результат:"), 1, out)


class CodexSetRefusalTest(CanaryParallelSandbox):
    codex_roles = ("developer",)

    def test_ac4_codex_set_refused_before_origin_profile_and_clone(self):
        """Набор с ролями Codex и `--parallel` — именованный отказ.

        Отказ называет набор и роли; до него нет ни обращения к origin
        (`_resolve_target_sha`, `fetch_ref_sha`), ни замка профиля, ни клона,
        ни записи реестра, ни дочернего процесса.

        Ловит мутацию: проверка `codex_roles` стоит после
        `_locked_canary_profile` или после `_resolve_target_sha` — замок или
        обращение к origin уже случились; либо отказ называет только первую
        роль.
        """
        for roles in (("developer",), ("developer", "reviewer")):
            with self.subTest(roles=roles):
                self.codex_roles = roles
                self.children = {"alfa": {}, "beta": {}}
                run = self.run_parallel(["alfa", "beta"])
                self.assertIsInstance(run.exc, SystemExit, run.describe())
                text = str(run.exc.code)
                self.assertIn(f"canary: --parallel недоступен для набора {SET_NAME}: "
                              f"роли ", text)
                self.assertIn(" на провайдере codex — профиль Codex канарейки один "
                              "на машину; веди прогон без --parallel", text)
                if len(roles) == 1:
                    self.assertIn(f"роли {roles[0]} на провайдере codex", text)
                for role in roles:
                    self.assertIn(role, text)
                self.assertEqual(self.resolve_calls, [])
                self.assertEqual(self.forbidden, [])
                self.assertEqual(run.attempts, [])
                self.assertEqual(self.listing(), [])


class RunTaskShaFormTest(CanaryParallelSandbox):
    STAMP = "20310305T101500Z"

    def put_mark(self):
        self.registry.mkdir(parents=True, exist_ok=True)
        mark = self.registry / f"{self.STAMP}.lock"
        mark.write_text(f"{os.getppid()}\n", encoding="utf-8")
        return mark

    def run_task(self, sha):
        template = self.pool / "alfa.md"
        with mock.patch.object(canary, "_run_one_task") as drive:
            try:
                artel._cmd_canary(["run-task", "--stamp", self.STAMP, "--template",
                                   str(template), "--sha", sha, "--set", SET_NAME,
                                   "--summary", SUMMARY])
            except SystemExit as exc:
                return exc, drive
        return None, drive

    def test_ac9_sha_not_full_form_refused_before_record(self):
        """`canary run-task --sha` не по форме полного sha — отказ до реестра.

        Короткий, в верхнем регистре, с лишним символом и с не-hex символом:
        ненулевой выход с текстом отказа, в каталоге реестра только метка, строк
        `canary_runs` нет, ведение и клон не вызваны; полный sha проходит.

        Ловит мутацию: сверка формы без якоря (`re.match` вместо `fullmatch`) —
        sha с лишним символом проходит до ведения; либо сверка без учёта
        регистра — верхний регистр проходит.
        """
        mark = self.put_mark()
        bad = {"короткий": SHORT_SHA, "верхний регистр": FULL_SHA.upper(),
               "лишний символ": FULL_SHA + "0", "не hex": "g" + FULL_SHA[1:]}
        for name, sha in bad.items():
            with self.subTest(name):
                exc, drive = self.run_task(sha)
                self.assertIsInstance(exc, SystemExit)
                self.assertNotIn(exc.code, (0, None))
                self.assertIn(f"canary run-task: --sha {sha} — не полный "
                              f"40-символьный sha", str(exc.code))
                drive.assert_not_called()
                self.assertEqual(self.listing(), [f"{self.STAMP}.lock"])
                self.assertEqual(mark.read_text(), f"{os.getppid()}\n")
                self.assertEqual(self.rows(), [])
                self.assertEqual(self.forbidden, [])
        exc, drive = self.run_task(FULL_SHA)
        self.assertIsNone(exc)
        drive.assert_called_once()
