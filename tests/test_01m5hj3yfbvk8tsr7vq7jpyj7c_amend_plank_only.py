"""`amend-tests` для файлов с меткой `AC-<n>: ` при пустом перечне долгоживущих файлов лока (оба пути), удаление долгоживущего файла с меткой с переносом имени теста в планку и отказ решения профиля записи из нескольких компонентов на `approve` гейта SPEC (AC-1..AC-5).

Группа: долгоживущий
Зелёный с рождения: задача только исполняет тестами пути кода пульта, верные на базе ветки (`amend._amend_plank_only`, путь `--from-branch` без перечня, перенос имени в `amend._labelled_long_lived_errors`, отказ решения профиля в `fsm._replaced_tests_declaration`), код пульта не меняется.

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`
через песочницы `AmendSandbox` и `ReplacedSandbox` соседних файлов),
связка «запись проекта — правило планки — ссылка документов — кодовая
ветка — лок — журнал» и «запись проекта — решение профиля — `approve` —
журнал». Учебный внешний проект с компонентом `pult-vitest` (правило
планки не по умолчанию); задача в `in_dev` с локом, планка — файл с меткой
`.test.jsx`, `.md` и пустой перечень сумм (или без перечня), долгоживущих
файлов нет. Правка Оператора: в рабочей копии — файлы планки в рабочей
копии кода; в `--from-branch` — коммит в ссылку документов. Сухой сбор и
прогон Vitest — шпион `subprocess.Popen` песочницы, без Node и сети.
Наблюдаются вывод команды, запись журнала «amend-tests отклонён», голова
ссылки документов, голова кодовой ветки, `tests_locked_sha`, число записей
«правка планки», дерево головы кодовой ветки и перечень нового лока.

Имена проектов, файлов, тестов и номера критериев — из `random`; зерно
печатается и входит в текст каждого провала.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from orchestrator import (checkpoint, config, project_profile, repo_context,
                          store, targets, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates
from orchestrator.advance_gates import mandate
from scripts import guard
from tests.sandbox import make_project_repo
from tests.test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled import (
    AmendSandbox, spec_text, ulid)
from tests.test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve import (
    ReplacedSandbox)

TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
TRACE = "трассируемость AC нарушена:"
GROUPS = "строка группы:"
LONG = "долгоживущие файлы tests/:"
REFUSED_OUT = "amend-tests: отказ"
DECISION_PREFIX = ("раздел «Заменяемые тесты» не сверить — решение профиля "
                   "тестов проекта: отказ:")


def has_criterion(text: str, n: int) -> bool:
    """`AC-<n>` в тексте как номер целиком (`AC-1` не находится в `AC-12`)."""
    return re.search(rf"AC-{n}(?!\d)", text) is not None


class PlankOnlySandbox(AmendSandbox):
    """`AmendSandbox` с задачей без долгоживущих файлов: перечень лока
    пуст (или его нет), планка — один файл с меткой на все критерии и `.md`."""

    def plank_only(self, manifest_file: bool = True, ban: bool = False):
        """Задача `in_dev` с локом: SPEC на 2–3 критерия, планка — `.test.jsx`
        с меткой на каждый критерий (`ban` — с запретом), `.md` и пустой
        перечень (`manifest_file=False` — без файла перечня)."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура правки планки", "in_dev",
                          branch, self.name, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        criteria = tuple(range(1, self.rng.randint(2, 3) + 1))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch, wt=Path(wt),
                            criteria=criteria)
        t.docs = config.PROJECTS / self.name / TASKS_DIR / tid
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid, criteria),
                                        encoding="utf-8")
        t.md = f"n{self.word()}.md"
        t.jsx = f"{self.word()}.test.jsx"
        t.plank = {t.md: f"заметка {self.word()}\n",
                   t.jsx: self.plank_jsx(criteria, ban=ban)}
        if manifest_file:
            t.plank[guard.LONG_LIVED_MANIFEST_NAME] = (
                guard.render_long_lived_manifest({}))
        folder = t.docs / PLANK_DIR
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in t.plank.items():
            (folder / name).write_text(text, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "developer")
        head = self.docs_head(t)
        self.assertTrue(head, self.note("ссылки документов нет"))
        store.update_task(self.conn, tid, tests_locked_sha=head)
        store.record_fixation(self.conn, tid)
        row = store.get_task(self.conn, tid)
        self.assertEqual(acceptance_gates.long_lived_manifest(tid, row, self.name),
                         ({}, ""), self.note("фикстура: перечень лока не пуст"))
        rule = project_profile.plank_rule(self.name)
        self.assertFalse(t.jsx.startswith("test_"),
                         self.note(f"фикстура: имя {t.jsx} на test_"))
        self.assertTrue(rule.is_labelled(t.jsx),
                        self.note(f"фикстура: {t.jsx} не файл с меткой"))
        return t

    def edit(self, t, from_branch: bool, files: dict, removed=()) -> tuple:
        """Правка планки Оператора (`files` поверх планки лока, `removed` —
        удалить) рабочей копией либо коммитом в ссылку документов;
        состояние до команды."""
        if from_branch:
            self.docs_commit(t, files, removed)
        else:
            plank = {n: v for n, v in t.plank.items() if n not in removed}
            plank.update(files)
            self.wt_plank(t, plank)
        return self.state_of(t)

    def case(self, kind: str, from_branch: bool) -> None:
        """Случай отказа `kind` в пути `from_branch`: отказ до любой записи
        с префиксом группы; в группе строк — имя файла с меткой, в
        трассируемости — номер снятого критерия."""
        t = self.plank_only(ban=kind == "только .md")
        needle, lost = "", ()
        if kind == "запрет":
            files, removed = {t.jsx: self.plank_jsx(t.criteria, ban=True)}, ()
            prefix, needle = GROUPS, guard.PLANK_BAN_TAIL
        elif kind == "нет строки группы":
            files, removed = {t.jsx: self.plank_jsx(t.criteria, group=False)}, ()
            prefix = GROUPS
        elif kind == "только .md":
            files, removed = {t.md: t.plank[t.md] + f"ещё {self.word()}\n"}, ()
            prefix, needle = GROUPS, guard.PLANK_BAN_TAIL
        elif kind == "трассируемость":
            dropped = self.rng.choice(t.criteria)
            kept = [n for n in t.criteria if n != dropped]
            files, removed = {t.jsx: self.plank_jsx(kept)}, ()
            prefix, lost = TRACE, (dropped,)
        else:
            files, removed = {}, (t.jsx,)
            prefix, lost = TRACE, t.criteria
        before = self.edit(t, from_branch, files, removed)
        out = self.assert_refused(t, self.amend(t, from_branch), before, prefix,
                                  needle)
        context = self.note(f"{kind}, from_branch={from_branch}:\n{out}")
        if prefix == GROUPS:
            self.assertIn(t.jsx, out, context)
        for n in lost:
            self.assertTrue(has_criterion(out, n), self.note(
                f"нет AC-{n} в отказе; {context}"))

    def valid(self, from_branch: bool) -> None:
        """Годная правка файла с меткой при пустом перечне и без перечня:
        проход, лок на голове ссылки документов, кодовая ветка прежняя."""
        for manifest_file in (True, False):
            with self.subTest(manifest_file=manifest_file, seed=self.seed):
                t = self.plank_only(manifest_file=manifest_file)
                n = self.rng.choice(t.criteria)
                edited = t.plank[t.jsx] + (
                    f"it('AC-{n}: ещё {self.word()}', () => "
                    f"{{ expect({n}).toBe({n}); }});\n")
                before = self.edit(t, from_branch, {t.jsx: edited})
                out = self.amend(t, from_branch)
                after = self.assert_passed(t, out, before)
                self.assertEqual(after[1], before[1], self.note(
                    f"голова кодовой ветки сдвинута:\n{out}"))


# ---------------------------------------------------------------- AC-1

class Ac1WorktreeValidTest(PlankOnlySandbox):

    def test_ac1_worktree_valid_labelled_edit_moves_lock_without_manifest(self):
        """Рабочая копия, пустой перечень лока и лок без перечня: годная правка файла с меткой сдвигает лок.

        Сценарий: задача `in_dev` с локом, планка — `<случайное>.test.jsx` с
        меткой на каждый критерий, `.md` и пустой перечень (второй прогон —
        лок без файла перечня); `long_lived_manifest` даёт `({}, "")`. В
        файл с меткой рабочей копии добавлен ещё один годный тест
        `AC-<n>`. Вывод без «amend-tests: отказ»; `tests_locked_sha` сдвинут
        и равен голове ссылки документов; записей «правка планки» на одну
        больше; голова кодовой ветки прежняя.

        Ловит мутацию: трассируемость в `_amend_plank_only` зовётся без
        правила планки (`acceptance_traceability_errors(tdir)`) — тесты
        `it('AC-<n>: …')` не видны, отказ «трассируемость AC нарушена:», лок
        не сдвинут.
        """
        self.valid(from_branch=False)


# ---------------------------------------------------------------- AC-2

class Ac2WorktreeRefusalTest(PlankOnlySandbox):

    def test_ac2_worktree_ban_in_labelled_file_refused(self):
        """Рабочая копия: файл с меткой с числовым литералом в аргументах `it` — отказ «строка группы:» с «… — запрещено в тексте планки».

        Сценарий: задача без долгоживущих файлов и с пустым перечнем; в
        файл с меткой рабочей копии внесён запрет (`5000` третьим
        аргументом `it`). Вывод несёт «amend-tests: отказ — строка группы:»,
        `guard.PLANK_BAN_TAIL` и имя файла; последняя запись «amend-tests
        отклонён» начинается с «строка группы:»; голова ссылки документов,
        голова кодовой ветки, `tests_locked_sha` и число записей «правка
        планки» прежние.

        Ловит мутацию: профиль в `_amend_plank_only` не берётся
        (`profile = None`) либо файлы планки собираются без правила
        (`acceptance_test_files(tdir)`) — `.test.jsx` не проверяется,
        правка с запретом сдвигает лок.
        """
        self.case("запрет", from_branch=False)

    def test_ac2_worktree_labelled_file_without_group_line_refused(self):
        """Рабочая копия: файл с меткой без строки группы — отказ «строка группы:» с именем файла.

        Сценарий: задача без долгоживущих файлов; из файла с меткой рабочей
        копии убрана строка `// Группа: …`. Отказ «строка группы:» до
        любой записи, текст называет файл с меткой; четыре величины
        прежние.

        Ловит мутацию: `profile = None` в `_amend_plank_only` — проверка
        строк группы смотрит только `test_*.py`, файл с меткой без строки
        группы проходит и лок сдвигается.
        """
        self.case("нет строки группы", from_branch=False)

    def test_ac2_worktree_only_md_with_banned_labelled_file_refused(self):
        """Рабочая копия: изменён только `.md`, неизменённый файл с меткой несёт запрет — отказ «строка группы:» с `guard.PLANK_BAN_TAIL`.

        Сценарий: лок уже держит файл с меткой с запретом; правка Оператора
        меняет только `.md`. Отказ «строка группы:» с «… — запрещено в
        тексте планки» и именем файла с меткой; четыре величины прежние.

        Ловит мутацию: файлы планки собираются без правила
        (`acceptance_test_files(tdir)`) — неизменённый файл с запретом не
        проверяется, правка `.md` сдвигает лок.
        """
        self.case("только .md", from_branch=False)

    def test_ac2_worktree_broken_traceability_refused(self):
        """Рабочая копия: из файла с меткой убран тест критерия — отказ «трассируемость AC нарушена:» с номером критерия.

        Сценарий: файл с меткой переписан без `it('AC-<n>: …')` одного
        случайного критерия SPEC. Отказ «трассируемость AC нарушена:» до
        любой записи, текст называет `AC-<n>`; четыре величины прежние.

        Ловит мутацию: вызов `_refuse_traceability` в `_amend_plank_only`
        удалён — непокрытый критерий не останавливает правку, лок
        сдвигается.
        """
        self.case("трассируемость", from_branch=False)

    def test_ac2_worktree_removed_only_labelled_file_refused(self):
        """Рабочая копия: удалён единственный файл с меткой — отказ «трассируемость AC нарушена:» с номерами критериев.

        Сценарий: в планке рабочей копии остались `.md` и перечень, файла с
        меткой нет. Отказ «трассируемость AC нарушена:», текст называет
        каждый критерий SPEC `AC-<n>`; четыре величины прежние.

        Ловит мутацию: вызов `_refuse_traceability` в `_amend_plank_only`
        удалён — планка без тестов проходит, лок сдвигается.
        """
        self.case("удалён файл", from_branch=False)


# ---------------------------------------------------------------- AC-3

class Ac3FromBranchTest(PlankOnlySandbox):

    def test_ac3_from_branch_valid_labelled_edit_moves_lock_without_manifest(self):
        """`--from-branch`, пустой перечень и лок без перечня: годная правка файла с меткой коммитом в ссылку документов сдвигает лок.

        Сценарий: та же задача, что AC-1; в файл с меткой добавлен годный
        тест `AC-<n>` коммитом поверх головы ссылки документов. Вывод без
        «amend-tests: отказ»; `tests_locked_sha` равен голове ссылки
        документов; записей «правка планки» на одну больше; голова кодовой
        ветки прежняя.

        Ловит мутацию: трассируемость `--from-branch` считается без правила
        планки — тесты с меткой не видны, отказ «трассируемость AC
        нарушена:», лок не сдвинут.
        """
        self.valid(from_branch=True)

    def test_ac3_from_branch_ban_in_labelled_file_refused(self):
        """`--from-branch`: файл с меткой с запретом — отказ «строка группы:» с `guard.PLANK_BAN_TAIL` и именем файла.

        Сценарий: коммитом в ссылку документов файл с меткой получает
        `5000` в аргументах `it`. Отказ до сдвига лока: голова ссылки
        документов (после коммита Оператора), голова кодовой ветки,
        `tests_locked_sha` и число записей «правка планки» прежние; вывод и
        запись «amend-tests отклонён» — с «строка группы:».

        Ловит мутацию: `by_rule` требует непустого перечня (`… and
        bool(manifest)`) — проверяются только `test_*.py`, файл с запретом
        входит в лок.
        """
        self.case("запрет", from_branch=True)

    def test_ac3_from_branch_labelled_file_without_group_line_refused(self):
        """`--from-branch`: файл с меткой без строки группы — отказ «строка группы:» с именем файла.

        Сценарий: коммитом в ссылку документов из файла с меткой убрана
        строка группы. Отказ «строка группы:» до сдвига лока; четыре
        величины прежние.

        Ловит мутацию: `by_rule` с `bool(manifest)` — при пустом перечне
        файлы с меткой не проверяются, правка проходит.
        """
        self.case("нет строки группы", from_branch=True)

    def test_ac3_from_branch_only_md_with_banned_labelled_file_refused(self):
        """`--from-branch`: коммит меняет только `.md`, неизменённый файл с меткой несёт запрет — отказ «строка группы:».

        Сценарий: лок держит файл с меткой с запретом; коммит в ссылку
        документов правит только `.md`. Отказ «строка группы:» с
        `guard.PLANK_BAN_TAIL` и именем файла с меткой; четыре величины
        прежние.

        Ловит мутацию: `by_rule` с `bool(manifest)` — состав файлов планки
        без правила, неизменённый файл с запретом не проверяется, лок
        сдвигается.
        """
        self.case("только .md", from_branch=True)

    def test_ac3_from_branch_broken_traceability_refused(self):
        """`--from-branch`: коммит убирает тест критерия из файла с меткой — отказ «трассируемость AC нарушена:» с номером критерия.

        Сценарий: коммитом в ссылку документов файл с меткой переписан без
        теста одного случайного критерия. Отказ «трассируемость AC
        нарушена:», текст называет `AC-<n>`; четыре величины прежние.

        Ловит мутацию: вызов `_refuse_traceability` пути `--from-branch`
        удалён — непокрытый критерий проходит, лок сдвигается.
        """
        self.case("трассируемость", from_branch=True)

    def test_ac3_from_branch_removed_only_labelled_file_refused(self):
        """`--from-branch`: коммит удаляет единственный файл с меткой — отказ «трассируемость AC нарушена:».

        Сценарий: коммитом в ссылку документов удалён файл с меткой, в
        планке остались `.md` и перечень. Отказ «трассируемость AC
        нарушена:», текст называет каждый `AC-<n>` SPEC; четыре величины
        прежние.

        Ловит мутацию: вызов `_refuse_traceability` пути `--from-branch`
        удалён — планка без тестов входит в лок.
        """
        self.case("удалён файл", from_branch=True)


# ---------------------------------------------------------------- AC-4

class Ac4LongLivedMovedNameTest(AmendSandbox):

    def removal(self, from_branch: bool) -> None:
        """Удаление долгоживущего файла с меткой, чьё имя теста перенесено
        в файл планки с меткой: проход, файла нет в голове кодовой ветки,
        перечень нового лока пуст."""
        t = self.locked()
        names = guard.plank_test_names(t.long_text)
        self.assertTrue(names, self.note("фикстура: у долгоживущего файла нет имён"))
        moved = "".join(f"it('{name}', () => {{ expect(1).toBe(1); }});\n"
                        for name in names)
        edited = t.plank[t.jsx] + moved
        self.assertTrue(set(names) <= set(guard.plank_test_names(edited)),
                        self.note("фикстура: имя не перенесено"))
        if from_branch:
            self.docs_commit(t, {t.jsx: edited})
            self.commit_code(t, t.long_rel, None)
        else:
            self.wt_plank(t, dict(t.plank, **{t.jsx: edited}))
            (t.wt / t.long_rel).unlink()
        before = self.state_of(t)
        out = self.amend(t, from_branch)
        after = self.assert_passed(t, out, before)
        context = self.note(f"from_branch={from_branch}:\n{out}")
        if not from_branch:
            self.assertNotEqual(after[1], before[1], context)
        tree = self.git("-C", str(t.wt), "ls-tree", "-r", "--name-only",
                        t.branch).split()
        self.assertNotIn(t.long_rel, tree, context)
        self.assertEqual(self.manifest(t), {}, context)

    def test_ac4_worktree_removal_with_name_moved_to_plank_passes(self):
        """Рабочая копия: долгоживущий файл с меткой удалён, его имя теста перенесено в файл планки с меткой — проход.

        Сценарий: задача с долгоживущим файлом с меткой и непустым
        перечнем; имена `guard.plank_test_names` долгоживущего файла
        добавлены тестами в `.test.jsx` планки рабочей копии, сам файл
        удалён из рабочей копии. Вывод без «amend-tests: отказ»;
        `tests_locked_sha` равен голове ссылки документов; записей «правка
        планки» на одну больше; голова кодовой ветки сдвинута коммитом
        удаления, удалённого файла нет в её дереве; перечень нового лока
        пуст или отсутствует.

        Ловит мутацию: в `_labelled_long_lived_errors` имена собираются
        только из долгоживущих файлов (`for label, text in items:`) —
        перенесённое имя не видно, отказ «удаление снимает методы».
        """
        self.removal(from_branch=False)

    def test_ac4_from_branch_removal_with_name_moved_to_plank_passes(self):
        """`--from-branch`: удаление долгоживущего файла с меткой коммитом кодовой ветки при перенесённом имени — проход.

        Сценарий: та же задача; имя теста перенесено коммитом в ссылку
        документов, долгоживущий файл удалён коммитом кодовой ветки. Вывод
        без «amend-tests: отказ»; `tests_locked_sha` равен голове ссылки
        документов; записей «правка планки» на одну больше; удалённого
        файла нет в дереве головы кодовой ветки; перечень нового лока пуст
        или отсутствует.

        Ловит мутацию: `for label, text in items:` в
        `_labelled_long_lived_errors` — файлы планки не дают имён, отказ
        «долгоживущие файлы tests/:», лок не сдвинут.
        """
        self.removal(from_branch=True)


# ---------------------------------------------------------------- AC-5

class Ac5MultiComponentDecisionTest(ReplacedSandbox):

    def multi_project(self) -> SimpleNamespace:
        """Учебный проект с записью из двух компонентов `pult-vitest`, у
        каждого непустое `paths`; в голове `main` — файл теста первого."""
        name = f"m{self.word()}"
        dirs = [f"d{self.word()}" for _ in range(2)]
        comps = [f"c{self.word()}" for _ in range(2)]
        body = "    components:\n"
        for comp, folder in zip(comps, dirs):
            fields = self.vitest_fields()
            fields["tests"] = f"[{folder}/**/*.test.jsx]"
            fields["long_lived"] = f"{folder}/<dir>/<name>.<id>.test.jsx"
            fields["weakening_scope"] = f"[{folder}/**]"
            fields["mutation_claim_scope"] = f"[{folder}/**]"
            fields["plank_layout"] = f"{folder}/.pv{self.word(5)}/<id>"
            fields["paths"] = f"[^{folder}/]"
            body += "".join(self.component_lines(comp, fields))
        self.append_entry(
            "  {name}:\n    forge: github\n    url: file:///nonexistent/{name}\n"
            "    base: main\n    token_slot: {name}-token\n    no_paths: []\n"
            "    project_skills: []\n    merge_gate: operator\n".format(name=name)
            + body)
        clone = make_project_repo(name)
        rel = f"{dirs[0]}/{self.word(5)}/{self.word()}.test.jsx"
        files = {"package.json": '{"name": "web"}\n',
                 rel: f"it('тест {self.word()}', () => {{}});\n"}
        for path, text in files.items():
            (clone / path).parent.mkdir(parents=True, exist_ok=True)
            (clone / path).write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comps[0], kind="multi",
                               tests=[rel], outside="", clone=clone)

    def test_ac5_multi_component_decision_refusal_on_approve(self):
        """Запись из двух компонентов с `paths`: `approve` гейта SPEC с разделом «Заменяемые тесты» — мягкий отказ с причиной решения профиля.

        Сценарий: проект с записью `components` из двух компонентов, у
        каждого непустое `paths`; фикстурно `repo_context.resolve` не
        `None`, `project_profile.decide(...).refusal` несёт
        `targets.MULTI_COMPONENT_PENDING`. Задача проекта на `spec_gate`,
        SPEC с годным разделом «Заменяемые тесты» (идентификатор файла
        первого компонента) и матрицей. `approve`: задача остаётся на
        `spec_gate`; последняя запись «approve отклонён» начинается с
        «раздел «Заменяемые тесты» не сверить — решение профиля тестов
        проекта: отказ:» и несёт причину решения; записи
        `mandate.REPLACED_TESTS_ACTION` нет.

        Ловит мутацию: отказ решения профиля учитывается только у артели
        (`decision.refusal and repo_context.is_artel(...)`) — запись
        «approve отклонён» несёт текст «вне границы» без причины решения.
        """
        project = self.multi_project()
        self.assertIsNotNone(repo_context.resolve(project.name),
                             self.note("фикстура: контекст проекта не разрешён"))
        reason = project_profile.decide(project.name).refusal
        self.assertTrue(reason, self.note("фикстура: решение без отказа"))
        self.assertIn(targets.MULTI_COMPONENT_PENDING, reason,
                      self.note(f"фикстура: причина {reason}"))
        cid = project_profile.test_id(project.comp, project.tests[0],
                                      self.vitest_name())
        n = self.rng.randint(1, 3)
        t = self.task(project, lambda tid: self.spec(tid, n,
                                                     [self.line(cid, n)]))
        out = self.approve(t)
        detail = self.assert_soft_refusal(t, out, reason)
        context = self.note(f"запись: {detail}\nвывод:\n{out}")
        self.assertTrue(detail.startswith(DECISION_PREFIX), context)
        self.assertNotIn(mandate.REPLACED_TESTS_ACTION,
                         [a for a, _d in self.rows(t)], context)


if __name__ == "__main__":
    unittest.main()
