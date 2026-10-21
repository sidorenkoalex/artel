"""AC-1: подкоманда `canary run-task` — отказ под ролью, разбор пяти аргументов, справка, без origin и без метки, отказ набора с ролями Codex.

Группа: разовый
Красен до реализации: диспетчер `_cmd_canary` не знает `run-task` — вызов уходит в ветку прогона `cmd_canary` и отказывает «нужен параметр --k» до подкоманды: принятый `--summary ""` не доходит до ведения задачи, текста отказа набора Codex нет.

Почему разовый: критерий сам называет подменяемые закрытые имена
(`_resolve_target_sha`, `_role_allowed_command`) и требует подменить
ведение задачи и план набора (`_run_one_task`, `_set_plan`) — правила
долгоживущего файла `tests/` такие подмены запрещают.

Песочница — `tests.sandbox.InitializedTmpRootTest` (пути `config` во
временном каталоге, БД со схемой). Подкоманда — диспетчером `artel.main()`
в процессе теста (`_runtask.invoke`). Ведение задачи подменено
(`canary._run_one_task`), план набора — подменённый `canary._set_plan`.
Родитель — `os.getppid()` процесса теста: его метка `<run_stamp>.lock`
раскладывается файлом. Значения аргументов порождаются от зерна; зерно
печатается и входит в текст провала.
"""
import contextlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin, invoke, plan  # noqa: E402

from orchestrator import artel, canary, config, runner  # noqa: E402
from tests.sandbox import InitializedTmpRootTest  # noqa: E402

FLAGS = ("--stamp", "--template", "--sha", "--set", "--summary")
CODEX_TEXT = ("canary run-task: набор {name} с ролями на провайдере codex не "
              "ведётся отдельным процессом — профиль Codex канарейки один на машину")


class RunTaskParseTest(RunTaskMixin, InitializedTmpRootTest):
    """Подкоманда в процессе теста; ведение задачи и план набора подменены."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()

    # ------------------------------------------------------------ фикстуры

    def values(self) -> dict:
        return {"--stamp": self.stamp(), "--template": str(self.template),
                "--sha": self.sha, "--set": "nabor-" + self.token(5),
                "--summary": f"developer → model-{self.token(4)}; источник: набор"}

    @staticmethod
    def flat(pairs) -> list:
        return [item for pair in pairs for item in pair]

    def refusal_cases(self) -> list:
        """(название, argv после `run-task`, run_stamp для метки либо None)."""
        cases = []
        for flag in FLAGS:
            v = self.values()
            cases.append((f"нет {flag}",
                          self.flat((f, v[f]) for f in FLAGS if f != flag),
                          v["--stamp"]))
        for bad in ("20310101T000000", "20310101T000000Zx", "2031-01-01T00:00:00Z",
                    "x" + self.stamp(), "20310101t000000z"):
            v = self.values()
            v["--stamp"] = bad
            cases.append((f"--stamp {bad!r}", self.flat((f, v[f]) for f in FLAGS),
                          bad))
        for flag in FLAGS:
            v = self.values()
            cases.append((f"повтор {flag}",
                          self.flat((f, v[f]) for f in FLAGS) + [flag, v[flag]],
                          v["--stamp"]))
        for flag in FLAGS:
            v = self.values()
            rest = self.flat((f, v[f]) for f in FLAGS if f != flag)
            cases.append((f"{flag} последним без значения", rest + [flag],
                          v["--stamp"]))
            others = [f for f in FLAGS if f != flag]
            following = self.rng.choice(others)
            order = [f for f in others if f != following]
            argv = self.flat((f, v[f]) for f in order)
            argv += [flag, following, v[following]]
            cases.append((f"{flag} перед {following}", argv, v["--stamp"]))
            cases.append((f"{flag} перед --lishniy", self.flat(
                (f, v[f]) for f in others) + [flag, "--lishniy"], v["--stamp"]))
        for extra in (["--detach"], ["--result-file", str(self.home / "r.json")],
                      ["--k", "1"], ["lishniy"]):
            v = self.values()
            cases.append((f"лишнее {extra}", self.flat((f, v[f]) for f in FLAGS)
                          + extra, v["--stamp"]))
        return cases

    def run_case(self, argv: list, plan_value, *, with_mark: bool, stamp) -> tuple:
        self.replaced.clear()
        with contextlib.ExitStack() as stack:
            spies = self.guards(stack)
            self.spy_replace(stack)
            spies["_set_plan"] = stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan_value))
            spies["_run_one_task"] = stack.enter_context(mock.patch.object(
                canary, "_run_one_task"))
            # Отвязанный запуск (`--detach`) породил бы настоящий процесс
            # пульта: шпион вместо него, его вызов — тоже не отказ разбора.
            spies["_detach_canary"] = stack.enter_context(mock.patch.object(
                artel, "_detach_canary"))
            mark = None
            if with_mark and stamp and "/" not in stamp:
                mark = self.put_mark(stamp, self.ppid)
            outcome = invoke(["canary", "run-task", *argv])
            listing = self.listing()
            if mark is not None:
                mark.unlink(missing_ok=True)
        return outcome, spies, listing

    # -------------------------------------------------------------- AC-1

    def test_ac1_role_refused_and_not_allowed(self):
        """Процесс роли вызывает `canary run-task` с полным набором аргументов.

        Наблюдение: отказ с ненулевым кодом текстом «artel.py canary
        run-task: команда недоступна процессу роли …», каталог реестра пуст,
        план и ведение задачи не звались; `_role_allowed_command("canary",
        ["run-task", …])` ложен.

        Ловит мутацию: `run-task` внесён в белый список ролей (например, как
        «внутренняя» подкоманда рядом с `observe show`) — роль запускает
        подкоманду, отказа нет, в реестре появляется запись.
        """
        v = self.values()
        argv = self.flat((f, v[f]) for f in FLAGS)
        self.assertFalse(artel._role_allowed_command("canary", ["run-task", *argv]),
                         self.msg("canary run-task разрешена роли"))
        with mock.patch.object(runner, "in_role_environment", return_value=True), \
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
            outcome, spies, listing = self.run_case(
                argv, plan(v["--set"], v["--summary"]), with_mark=False, stamp=None)
        self.assertNotEqual(outcome.code, 0, self.msg(outcome))
        self.assertIn("artel.py canary run-task: команда недоступна процессу роли",
                      outcome.text, self.msg(outcome))
        self.assertEqual(listing, [], self.msg(outcome))
        self.assertFalse(spies["_run_one_task"].called, self.msg(outcome))
        self.assertFalse(spies["_set_plan"].called, self.msg(outcome))

    def test_ac1_help_does_not_name_run_task(self):
        """`artel.py --help` и докстринг модуля `artel` — справка пульта — не называют `run-task`.

        Ловит мутацию: подкоманда внесена в справку `artel.py` строкой
        «canary run-task …» — справка печатает `run-task`.
        """
        self.assertNotIn("run-task", artel.__doc__ or "", self.msg("докстринг artel"))
        outcome = invoke(["--help"])
        self.assertEqual(outcome.code, 0, self.msg(outcome))
        self.assertNotIn("run-task", outcome.text, self.msg(outcome))

    def test_ac1_bad_arguments_refused_with_empty_registry(self):
        """Каждый отказ разбора: пропуск любого из пяти аргументов, `--stamp` вне `RUN_STAMP_RE`, повтор флага, флаг без значения (последним и перед `--…`), лишний аргумент.

        Два прохода на случай. Без метки родителя: ненулевой код, каталог
        реестра пуст, замен в каталог реестра не было. С меткой родителя
        (`os.getppid()`), при которой правильный вызов дошёл бы до ведения:
        ненулевой код, ведение задачи не звалось, строк `canary_runs` нет,
        в каталоге реестра только метка теста.

        Ловит мутацию: разбор берёт значение флага по индексу без проверки
        (повтор, «флаг без значения» перед `--…`, лишний `--detach`/`--k`
        проходят), `--stamp` сверяется `match` вместо `fullmatch`
        (`…Zx` проходит), пропущенный `--summary` молча становится пустой
        строкой — подкоманда пишет запись реестра либо доходит до ведения.
        """
        for name, argv, stamp in self.refusal_cases():
            v_plan = plan(argv[argv.index("--set") + 1]
                          if "--set" in argv and argv.index("--set") + 1 < len(argv)
                          else "nabor", "")
            if "--summary" in argv and argv.index("--summary") + 1 < len(argv):
                v_plan = v_plan._replace(summary=argv[argv.index("--summary") + 1])
            for with_mark in (False, True):
                with self.subTest(случай=name, метка=with_mark):
                    rows_before = self.rows()
                    outcome, spies, listing = self.run_case(
                        argv, v_plan, with_mark=with_mark, stamp=stamp)
                    ctx = self.msg(f"{name}: argv {argv}; {outcome!r}")
                    self.assertNotEqual(outcome.code, 0, ctx)
                    self.assertEqual(self.replaced, [], ctx)
                    self.assertFalse(spies["_run_one_task"].called, ctx)
                    self.assertFalse(spies["_detach_canary"].called, ctx)
                    self.assertEqual(self.rows(), rows_before, ctx)
                    if with_mark:
                        self.assertEqual([n for n in listing if not n.endswith(".lock")],
                                         [], ctx)
                    else:
                        self.assertEqual(listing, [], ctx)

    def test_ac1_empty_summary_value_accepted(self):
        """`--summary ""` — пустая строка значением; план набора с пустой сводкой, метка родителя на месте.

        Наблюдение: отказа разбора нет — подменённое ведение задачи вызвано
        ровно один раз, код 0.

        Ловит мутацию: «флаг без значения» проверяется как «значение
        пусто» (`not rest[i + 1]`) — пустая сводка отказана разбором.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        argv = self.argv(stamp, set_name, "")[2:]
        outcome, spies, listing = self.run_case(argv, plan(set_name, ""),
                                                with_mark=True, stamp=stamp)
        self.assertEqual(outcome.code, 0, self.msg(outcome))
        self.assertEqual(spies["_run_one_task"].call_count, 1, self.msg(outcome))

    def test_ac1_no_origin_no_mark_created_or_removed(self):
        """Штатный вызов при метке родителя и вызов без метки.

        Наблюдение: подменённые `_resolve_target_sha` и
        `gitcmd.fetch_ref_sha` не вызваны ни разу; метка родителя во время
        подменённой задачи и после вызова — тот же файл (содержимое и inode);
        без метки — после вызова метки `<run_stamp>.lock` в каталоге нет.

        Ловит мутацию: подкоманда разрешает `--sha` прежним
        `_resolve_target_sha` (дополнение до полного sha, `fetch_ref_sha` без
        него), берёт реестр прежним `_live_run_record` (метка создаётся и
        снимается) либо снимает метку при снятии своей записи.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(6)
        mark = self.put_mark(stamp, self.ppid)
        shot = (mark.read_bytes(), mark.stat().st_ino)
        during = {}

        def task(*args, **kwargs):
            during["mark"] = (mark.read_bytes(), mark.stat().st_ino) if mark.exists() else None

        with contextlib.ExitStack() as stack:
            spies = self.guards(stack)
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan(set_name, summary)))
            stack.enter_context(mock.patch.object(canary, "_run_one_task",
                                                  side_effect=task))
            outcome = invoke(self.argv(stamp, set_name, summary))
        self.assertEqual(outcome.code, 0, self.msg(outcome))
        self.assertEqual(during.get("mark"), shot, self.msg(f"метка во время задачи; {outcome!r}"))
        self.assertTrue(mark.exists(), self.msg(f"метка снята; {outcome!r}"))
        self.assertEqual((mark.read_bytes(), mark.stat().st_ino), shot, self.msg(outcome))
        for name in ("_resolve_target_sha", "fetch_ref_sha"):
            self.assertFalse(spies[name].called, self.msg(f"{name}: {outcome!r}"))
        mark.unlink()

        other = self.stamp()
        with contextlib.ExitStack() as stack:
            spies = self.guards(stack)
            stack.enter_context(mock.patch.object(
                canary, "_set_plan", return_value=plan(set_name, summary)))
            stack.enter_context(mock.patch.object(canary, "_run_one_task"))
            outcome = invoke(self.argv(other, set_name, summary))
        self.assertNotIn(f"{other}.lock", self.listing(), self.msg(outcome))
        for name in ("_resolve_target_sha", "fetch_ref_sha"):
            self.assertFalse(spies[name].called, self.msg(f"{name}: {outcome!r}"))

    def test_ac1_codex_set_refused_before_registry_and_clone(self):
        """План набора с ролью на провайдере Codex (непустое `codex_roles`): без метки и с меткой родителя.

        Наблюдение: ненулевой код, текст «canary run-task: набор <имя> с
        ролями на провайдере codex не ведётся отдельным процессом — профиль
        Codex канарейки один на машину»; замен в каталог реестра не было,
        каталог реестра пуст (с меткой — в нём только метка теста); ведение
        задачи и клон не звались; профиль Codex (`_locked_canary_profile`,
        `_canary_profile_auth`, `_codex_clone_auth`) не тронут.

        Ловит мутацию: проверки `codex_roles` нет — подкоманда пишет запись
        и ведёт задачу (или берёт профиль Codex прежним путём
        `cmd_canary`); либо проверка стоит после записи реестра.
        """
        for with_mark in (False, True):
            with self.subTest(метка=with_mark):
                stamp, set_name = self.stamp(), "nabor-codex-" + self.token(4)
                summary = "developer → gpt-" + self.token(4)
                outcome, spies, listing = self.run_case(
                    self.argv(stamp, set_name, summary)[2:],
                    plan(set_name, summary, codex_roles=("developer",)),
                    with_mark=with_mark, stamp=stamp)
                ctx = self.msg(outcome)
                self.assertNotEqual(outcome.code, 0, ctx)
                self.assertIn(CODEX_TEXT.format(name=set_name), outcome.text, ctx)
                self.assertEqual(self.replaced, [], ctx)
                expected = [f"{stamp}.lock"] if with_mark else []
                self.assertEqual(listing, expected, ctx)
                for name in ("_run_one_task", "_ephemeral_clone",
                             "_locked_canary_profile", "_canary_profile_auth",
                             "_codex_clone_auth"):
                    self.assertFalse(spies[name].called, self.msg(f"{name}: {outcome!r}"))


if __name__ == "__main__":
    unittest.main()
