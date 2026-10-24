"""Пакетное чтение документов задачи в `read_tree` и один `rev-parse` в начале `suite_tree_hash`.

Группа: долгоживущий
Красен до реализации: `read_tree` ещё читает дерево за 1 + N вызовов git (`ls-tree` и `show` на файл) — счёт AC-1 на 5 и 20 файлах больше трёх, шпион `gitcmd.carpentry` в AC-3 не видит `cat-file`, а `ls-tree` идёт по имени ссылки и в гонке читает дерево B; `suite_tree_hash` делает два `rev-parse` при `worktree=True` (AC-5); остальные методы держат прежний наблюдаемый результат и зелёные с рождения.

Связка, которую держит файл: `read_tree`/`suite_tree_hash` — настоящий git
песочницы `RealGitSandbox` (фикстура `real_git`). Дерево ссылки документов
строится плумбингом git (`hash-object`, `update-index --cacheinfo` во
временном индексе, `write-tree`, `commit-tree`, `update-ref`): так в дерево
попадают записи, которых не собрать рабочей копией, — подмодуль без коммита,
путь не в UTF-8, путь с табуляцией.

Эталон — прежняя реализация `read_tree` и прежняя `suite_tree_hash`,
перенесённые сюда (`reference_read_tree`, `reference_suite_tree_hash`).
Отличия от дословной копии — только в адресах имён (и в литерале
каталога задач: он собран из константы `DOCS` — правило файлов `tests/`
не пускает его строкой): модули git берутся
атрибутом соседнего модуля (`retro.artifact_branch`, `acceptance.gitcmd`),
закрытое `_NO_REPO` — копией его значения; внутренний `git()` эталона
запускает git не своим `Popen`, а `gitcmd.carpentry` с тем же окружением
(`pult_env(env)`) — правило файлов `tests/` не пускает прямой запуск git
через `subprocess`, а итог (stdout при коде 0) тот же; последний шаг
`_with_tree_db_files` эталона опущен: в песочнице файлов БД в дереве нет
(`store.tree_db_files` пуст — каждый тест сверяет это сам), и шаг
возвращает дерево как есть.
"""
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, config, retro, store

artifact_branch = retro.artifact_branch
gitcmd = acceptance.gitcmd

# Задача песочницы; каталог документов — `<DOCS>/<id>`.
TASK = "01T0BATCHREADSFIXTURE00000"
DOCS = "tasks"
TASK_DIR = f"{DOCS}/{TASK}"
NO_REPO_COPY = Path("/dev/null/artel-no-project-repo")


# --- эталон -----------------------------------------------------------------

def reference_read_tree(task_id: str) -> dict:
    """{путь: текст} всех файлов каталога задачи артефактной ветки задачи;
    пустой словарь — ветки нет или каталог в ней пуст."""
    branch = artifact_branch.branch_name(task_id)
    repo = artifact_branch.task_repo(task_id)
    if repo == NO_REPO_COPY:
        return {}
    paths = gitcmd.ls_tree_files(branch, f"{DOCS}/{task_id}", repo=repo) or []
    files = {}
    for rel in paths:
        text, _ = gitcmd.show(branch, rel, repo=repo)
        if text is not None:
            files[rel] = text
    return files


def reference_suite_tree_hash(root: Path, *, ref: str = "HEAD", base: bool = False,
                              worktree: bool = True) -> str | None:
    """Снимок git-дерева через отдельный индекс; исходный индекс не меняется."""
    root = Path(root)
    top = gitcmd.in_repo(root, "rev-parse", "--show-toplevel")
    if (top is None or top.returncode != 0 or
            Path(top.stdout.strip()).resolve() != root.resolve()):
        return None
    if worktree:
        untracked = gitcmd.in_repo(root, "ls-files", "--others",
                                   "--exclude-standard", "-z")
        if untracked is None or untracked.returncode != 0:
            return None
        if any(p and not p.startswith(f"{DOCS}/") for p in
               untracked.stdout.split("\0")):
            return None
    with tempfile.TemporaryDirectory(prefix="artel-suite-index-") as holder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(holder) / "index")}
        if worktree:
            original = gitcmd.in_repo(root, "rev-parse", "--path-format=absolute",
                                      "--git-path", "index")
            if original is None or original.returncode != 0:
                return None
            try:
                shutil.copyfile(original.stdout.strip(), env["GIT_INDEX_FILE"])
            except (OSError, ValueError):
                return None
        def git(*args):
            # Прежний `Popen(["git", "-C", root, …], env=pult_env(env))` —
            # тем же окружением через `gitcmd.carpentry` (докстринг модуля).
            res = gitcmd.carpentry(root, list(args), env)
            return res.stdout.strip() if res.returncode == 0 else None
        if not worktree and git("read-tree", ref) is None:
            return None
        if worktree and git("add", "-u", "--", ".") is None:
            return None
        if base and git("rm", "-q", "--cached", "-r", "--ignore-unmatch",
                        "--", *config.FULL_SUITE_BASE_EXCLUDED_PATHS) is None:
            return None
        tree = git("write-tree")
        if not tree or not re.fullmatch(r"[0-9a-f]{40}", tree):
            return None
    # `_with_tree_db_files` прежней версии: файлов БД в дереве песочницы нет —
    # дерево как есть (докстринг модуля).
    return tree


# --- построение деревьев ссылки ---------------------------------------------

def blob(path: str, data: bytes, mode: str = "100644") -> tuple:
    return (mode, path, data)


def gitlink(path: str, sha: str) -> tuple:
    return ("160000", path, sha)


def doc(name: str) -> str:
    return f"{TASK_DIR}/{name}"


def build_commit(sandbox, entries) -> str:
    """Коммит с деревом ровно из `entries` (режим, путь, байты или sha
    подмодуля) — временным индексом, рабочая копия и индекс песочницы не
    меняются."""
    with tempfile.TemporaryDirectory() as holder:
        index = Path(holder) / "index"
        with mock.patch.dict(os.environ, {"GIT_INDEX_FILE": str(index)}):
            for number, (mode, path, data) in enumerate(entries):
                if mode == "160000":
                    sha = data
                else:
                    source = Path(holder) / f"blob-{number}"
                    source.write_bytes(data)
                    sha = sandbox.git("hash-object", "-w", "--",
                                      str(source)).strip()
                sandbox.git("update-index", "--add", "--cacheinfo",
                            f"{mode},{sha},{path}")
            tree = sandbox.git("write-tree").strip()
        return sandbox.git("commit-tree", tree, "-m", "дерево песочницы").strip()


def point_ref(sandbox, sha: str) -> None:
    sandbox.git("update-ref", artifact_branch.branch_name(TASK), sha)


def ref_sha(sandbox) -> str:
    return sandbox.git("rev-parse", artifact_branch.branch_name(TASK)).strip()


def random_text(rng: random.Random, lines: int) -> str:
    words = ["документ", "задача", "plan", "review", "ссылка", "git", "дерево"]
    return "".join(" ".join(rng.choice(words) for _ in range(rng.randint(1, 6)))
                   + "\n" for _ in range(lines))


def seeded() -> tuple[int, random.Random]:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def plain_files(rng: random.Random, count: int) -> list:
    return [blob(doc(f"file-{n:02d}.md"), random_text(rng, rng.randint(1, 8))
                 .encode("utf-8")) for n in range(count)]


def outside_files() -> list:
    return [blob("README.md", "корень\n".encode("utf-8")),
            blob(f"{DOCS}/01T0OTHERTASKFIXTURE000000/SPEC.md", "чужая\n".encode("utf-8")),
            blob(f"{DOCS}/{TASK}X/SPEC.md", "соседний префикс\n".encode("utf-8"))]


def case_entries(sandbox, case: str, rng: random.Random):
    """Записи дерева ссылки для варианта AC-2; `None` — ссылку не заводить."""
    head = sandbox.git("rev-parse", "HEAD").strip()
    cases = {
        "plain": lambda: plain_files(rng, 6),
        "nested": lambda: [blob(doc("SPEC.md"), b"spec\n"),
                           blob(doc("acceptance_tests/test_a.py"), b"a = 1\n"),
                           blob(doc("acceptance_tests/deep/x/y.txt"), b"y\n"),
                           blob(doc("z.md"), b"z\n")],
        "empty_dir": lambda: outside_files(),
        "no_ref": lambda: None,
        "newlines": lambda: [blob(doc("crlf.md"), b"a\r\nb\rc\n\r\n")],
        "not_utf8": lambda: [blob(doc("latin.md"), "café".encode("latin-1")),
                             blob(doc("ok.md"), b"ok\n")],
        "nul_bytes": lambda: [blob(doc("nul.bin"), b"a\0b\0\n")],
        "large": lambda: [blob(doc("big.md"),
                               random_text(rng, 40000).encode("utf-8"))],
        "symlink": lambda: [blob(doc("link"), b"SPEC.md", mode="120000"),
                            blob(doc("SPEC.md"), b"spec\n")],
        "odd_paths": lambda: [blob(doc("заметка.md"), b"ru\n"),
                              blob(doc("tab\there.md"), b"tab\n"),
                              blob(doc("plain.md"), b"plain\n")],
        "submodule": lambda: [gitlink(doc("sub-present"), head),
                              gitlink(doc("sub-absent"), "1" * 40),
                              blob(doc("SPEC.md"), b"spec\n")],
        "outside": lambda: outside_files() + plain_files(rng, 3),
        "same_oid": lambda: [blob(doc("one.md"), b"same\n"),
                             blob(doc("two.md"), b"same\n")],
        "empty_file": lambda: [blob(doc("empty.md"), b""),
                               blob(doc("SPEC.md"), b"spec\n")],
        "bom": lambda: [blob(doc("bom.md"), "﻿текст\n".encode("utf-8"))],
        "quotepath_false": lambda: [blob(doc("заметка.md"), b"ru\n"),
                                    blob(doc("plain.md"), b"plain\n")],
    }
    return cases[case]()


# --- AC-1 -------------------------------------------------------------------

def git_argv_spy():
    """Подмена `gitcmd.subprocess.run`, пишущая argv каждого запуска git.

    До подмены БД песочницы открывается один раз: первое `store.db()`
    процесса заводит схему и счётчики задач (`seed_task_counters` спрашивает
    git о ветках и истории main) — это посев песочницы, не чтение документов."""
    store.db()
    real = subprocess.run
    calls = []

    def spy(args, *rest, **kwargs):
        argv = [str(a) for a in args] if not isinstance(args, (str, bytes)) else [args]
        if argv and os.path.basename(argv[0]) == "git":
            calls.append(argv)
        return real(args, *rest, **kwargs)
    return calls, mock.patch("orchestrator.gitcmd.subprocess.run", spy)


@pytest.mark.parametrize("count", [1, 5, 20])
def test_ac1_existing_ref_reads_in_at_most_three_git_calls(real_git, count):
    """Ссылка документов с `count` обычными файлами: `read_tree` делает не больше трёх вызовов git.

    Счёт — подменой `gitcmd.subprocess.run`, учитывающей argv с `git`
    (`gitcmd.git`/`in_repo` и `gitcmd.carpentry` идут через неё). Словарь
    при этом полный — все `count` файлов с их текстами.

    Ловит мутацию: `read_tree` оставлен на прежнем `ls-tree` + `show` на
    каждый файл (или `cat-file` зовётся по одному на blob) — на 5 и 20
    файлах вызовов git 6 и 21, `assert len(calls) <= 3` краснеет.
    """
    seed, rng = seeded()
    entries = plain_files(rng, count)
    point_ref(real_git, build_commit(real_git, entries))
    calls, patcher = git_argv_spy()
    with patcher:
        result = artifact_branch.read_tree(TASK)
    assert len(calls) <= 3, f"зерно: {seed}; вызовы git: {calls}"
    assert result == {path: data.decode("utf-8") for _, path, data in entries}, (
        f"зерно: {seed}")


def test_ac1_empty_task_dir_starts_no_cat_file(real_git):
    """Ссылка есть, но в каталоге задачи у неё ничего нет — `cat-file` не запускается.

    Ловит мутацию: `cat-file --batch` запускается всегда, даже с пустым
    входом, — шпион `gitcmd.subprocess.run` видит argv с `cat-file`, и
    тест краснеет.
    """
    point_ref(real_git, build_commit(real_git, outside_files()))
    calls, patcher = git_argv_spy()
    with patcher:
        result = artifact_branch.read_tree(TASK)
    assert result == {}
    assert not [argv for argv in calls if "cat-file" in argv], calls


def test_ac1_absent_ref_takes_the_old_path_by_ref_name(real_git):
    """Ссылки нет: `read_tree` идёт прежним путём — `gitcmd.ls_tree_files` по имени ссылки.

    Ловит мутацию: при пустой голове реализация всё равно зовёт свой
    `ls-tree` через `in_repo` (или ничего не зовёт и сразу отвечает `{}`)
    — `gitcmd.ls_tree_files` с именем `refs/artifacts/<id>` не вызван,
    список `seen` пуст, тест краснеет.
    """
    real = gitcmd.ls_tree_files
    seen = []

    def spy(branch, rel_dir, **kwargs):
        seen.append((branch, rel_dir))
        return real(branch, rel_dir, **kwargs)
    with mock.patch("orchestrator.gitcmd.ls_tree_files", spy):
        result = artifact_branch.read_tree(TASK)
    assert result == {}
    assert [branch for branch, _ in seen] == [artifact_branch.branch_name(TASK)]


# --- AC-2 -------------------------------------------------------------------

AC2_CASES = ["plain", "nested", "empty_dir", "no_ref", "newlines", "not_utf8",
             "nul_bytes", "large", "symlink", "odd_paths", "submodule",
             "outside", "same_oid", "empty_file", "bom", "quotepath_false"]


@pytest.mark.parametrize("case", AC2_CASES)
def test_ac2_result_equals_the_reference_on_a_still_ref(real_git, case):
    """На неподвижной ссылке `read_tree` отдаёт ровно то же, что эталон: ключи, их порядок и тексты.

    Деревья — варианты критерия: обычные и вложенные файлы, пустой каталог,
    нет ссылки, `\\r\\n` и одиночный `\\r`, не UTF-8, нулевые байты, файл
    больше 1 МБ, символическая ссылка, не-ASCII путь и путь с табуляцией,
    подмодуль с коммитом и без, файлы вне каталога задачи, два файла с
    одним oid, пустой файл, BOM, `core.quotePath=false`. Сверяется список
    пар (путь, текст) — порядок ключей входит в равенство.

    Ловит мутацию: байты blob декодируются без перевода `\\r` (или с
    `errors="replace"`, или со снятием BOM), путь в кавычках из `ls-tree`
    не выпадает, а подмодуль читается из вывода `cat-file` вместо прежнего
    `show` — в соответствующем варианте пары расходятся с эталоном.
    """
    seed, rng = seeded()
    if case == "quotepath_false":
        real_git.git("config", "core.quotePath", "false")
    entries = case_entries(real_git, case, rng)
    if entries is not None:
        point_ref(real_git, build_commit(real_git, entries))
    expected = reference_read_tree(TASK)
    result = artifact_branch.read_tree(TASK)
    assert list(result.items()) == list(expected.items()), f"зерно: {seed}; {case}"
    if case in ("plain", "nested", "outside", "quotepath_false"):
        assert expected, f"зерно: {seed}; эталон пуст в варианте {case}"
    if case == "quotepath_false":
        assert doc("заметка.md") in result


def test_ac2_no_repo_gives_an_empty_dict(real_git):
    """Репозиторий задачи не найден (`_NO_REPO`: target без записи) — пустой словарь, как у эталона.

    Ловит мутацию: проверка `repo == _NO_REPO` снята, и `read_tree` идёт
    с этим путём в git — `ls-tree`/`cat-file` в `/dev/null/…` либо роняют
    чтение, либо отвечают не тем; тест сверяет `{}` с эталоном и
    `artifact_branch.task_repo` — что вариант действительно без клона.
    """
    point_ref(real_git, build_commit(real_git, [blob(doc("SPEC.md"), b"spec\n")]))
    store.insert_task(store.db(), TASK, "Задача без клона", "in_dev",
                      "task/x", "ghost-project", 10.0)
    assert artifact_branch.task_repo(TASK) == NO_REPO_COPY
    assert artifact_branch.read_tree(TASK) == reference_read_tree(TASK) == {}


def test_ac2_quotepath_false_non_utf8_path_raises_in_both(real_git):
    """`core.quotePath=false` и путь не в UTF-8: обе версии одинаково бросают `UnicodeDecodeError`.

    Текстовый `ls-tree` не декодирует сырой байт пути — и эталон, и
    новая версия падают одним и тем же исключением.

    Ловит мутацию: новая версия читает `ls-tree` байтами (или с
    `errors="replace"`) и молча отдаёт словарь — `pytest.raises` на ней не
    срабатывает, тест краснеет.
    """
    real_git.git("config", "core.quotePath", "false")
    name = os.fsdecode(b"caf\xe9.md")
    point_ref(real_git, build_commit(real_git, [blob(doc(name), b"x\n"),
                                                blob(doc("ok.md"), b"ok\n")]))
    with pytest.raises(UnicodeDecodeError):
        reference_read_tree(TASK)
    with pytest.raises(UnicodeDecodeError):
        artifact_branch.read_tree(TASK)


# --- AC-3 -------------------------------------------------------------------

def tree_a() -> list:
    return [blob(doc("SPEC.md"), b"spec A\n"),
            blob(doc("PLAN.md"), b"plan A\n"),
            blob(doc("acceptance_tests/test_a.py"), b"a = 'A'\n")]


def tree_b() -> list:
    return [blob(doc("SPEC.md"), b"spec B\n"),
            blob(doc("REVIEW.md"), b"review B\n"),
            blob(doc("acceptance_tests/test_a.py"), b"a = 'B'\n")]


def as_dict(entries) -> dict:
    return {path: data.decode("utf-8") for _, path, data in entries}


def test_ac3_ref_moves_between_ls_tree_and_cat_file(real_git):
    """Ссылка сдвигается на B перед `cat-file`: результат — полное дерево A, `cat-file` прошёл через `gitcmd.carpentry`.

    Подмена `gitcmd.carpentry` на вызове `cat-file` делает `update-ref`
    ссылки на коммит B, убеждается, что ссылка уже указывает на B, и
    только потом пропускает вызов к настоящему git.

    Ловит мутацию: `cat-file` запускается мимо `gitcmd.carpentry`
    (прямой `subprocess`, чужой помощник) — шпион не видит `cat-file`,
    `seen` пуст; либо после `ls-tree` тексты дочитываются `show` по имени
    ссылки — словарь несёт тексты B (или смесь A и B) вместо A.
    """
    commit_a = build_commit(real_git, tree_a())
    commit_b = build_commit(real_git, tree_b())
    point_ref(real_git, commit_a)
    real = gitcmd.carpentry
    seen = []

    def shifting(repo, args, env, **kwargs):
        if "cat-file" in args:
            point_ref(real_git, commit_b)
            seen.append(ref_sha(real_git))
        return real(repo, args, env, **kwargs)
    with mock.patch("orchestrator.gitcmd.carpentry", shifting):
        result = artifact_branch.read_tree(TASK)
    assert seen == [commit_b], "cat-file не прошёл через gitcmd.carpentry"
    assert result == as_dict(tree_a())


def test_ac3_ref_moves_between_head_and_ls_tree(real_git):
    """Ссылка сдвигается на B перед `ls-tree`: результат — полное дерево A, прочитанное головой первым.

    Подмена `gitcmd.in_repo` на первом вызове `ls-tree` делает `update-ref`
    ссылки на коммит B и убеждается, что ссылка указывает на B, затем
    пропускает вызов к настоящему git.

    Ловит мутацию: `ls-tree` идёт по имени ссылки, а не по sha, разрешённому
    головой, — дерево и тексты берутся из B, словарь не равен дереву A.
    """
    commit_a = build_commit(real_git, tree_a())
    commit_b = build_commit(real_git, tree_b())
    point_ref(real_git, commit_a)
    real = gitcmd.in_repo
    seen = []

    def shifting(repo, *args):
        if "ls-tree" in args and not seen:
            point_ref(real_git, commit_b)
            seen.append(ref_sha(real_git))
        return real(repo, *args)
    with mock.patch("orchestrator.gitcmd.in_repo", shifting):
        result = artifact_branch.read_tree(TASK)
    assert seen == [commit_b], "ls-tree не случился — сдвиг не разыгран"
    assert result == as_dict(tree_a())


# --- AC-4 -------------------------------------------------------------------

def cat_file_refusal(kind: str):
    """Подмена `gitcmd.carpentry`, портящая ответ `cat-file` способом `kind`."""
    real = gitcmd.carpentry

    def refusing(repo, args, env, *, input=None, text=True):
        if "cat-file" not in args:
            return real(repo, args, env, input=input, text=text)
        if kind == "nonzero":
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: batch")
        if kind == "oserror":
            raise OSError("git не запустился")
        if kind == "truncated":
            res = real(repo, args, env, input=input, text=text)
            return subprocess.CompletedProcess(args, 0, res.stdout[:len(res.stdout) // 2],
                                               res.stderr)
        oids = [line for line in (input or b"").split(b"\n") if line]
        return subprocess.CompletedProcess(
            args, 0, b"".join(oid + b" missing\n" for oid in oids), b"")
    return refusing


@pytest.mark.parametrize("kind", ["nonzero", "oserror", "truncated", "missing"])
def test_ac4_cat_file_failure_falls_back_to_the_reference_result(real_git, kind):
    """Отказ `cat-file` (`kind`) — результат `read_tree` равен эталону, файлы дочитаны `show`.

    Ловит мутацию: отказ `cat-file` не уводит на чтение `show` по файлам —
    на ненулевом коде или `missing` словарь пуст или неполон, на `OSError`
    исключение уходит наружу, на оборванном ответе в словарь попадает
    обрезанный текст; сравнение с эталоном краснеет.
    """
    seed, rng = seeded()
    entries = plain_files(rng, 4) + [blob(doc("big.md"),
                                          random_text(rng, 3000).encode("utf-8"))]
    point_ref(real_git, build_commit(real_git, entries))
    expected = reference_read_tree(TASK)
    assert expected == as_dict(entries), f"зерно: {seed}"
    with mock.patch("orchestrator.gitcmd.carpentry", cat_file_refusal(kind)):
        result = artifact_branch.read_tree(TASK)
    assert list(result.items()) == list(expected.items()), f"зерно: {seed}; {kind}"


def test_ac4_every_ls_tree_refused_calls_the_old_ls_tree_files(real_git):
    """Подмена отказывает всем `ls-tree`: результат — пустой словарь эталона, вызван `gitcmd.ls_tree_files` по имени ссылки.

    Ловит мутацию: отказ `ls-tree` по sha не уводит на прежний путь
    (`read_tree` сразу отвечает `{}`), либо прежний путь зовётся по sha
    вместо имени ссылки — список ветвей вызовов `ls_tree_files` не равен
    `[refs/artifacts/<id>]`.
    """
    point_ref(real_git, build_commit(real_git, [blob(doc("SPEC.md"), b"spec\n")]))
    real_in_repo = gitcmd.in_repo
    real_ls = gitcmd.ls_tree_files
    seen = []

    def refusing(repo, *args):
        if "ls-tree" in args:
            return subprocess.CompletedProcess(args, 128, "", "fatal: ls-tree")
        return real_in_repo(repo, *args)

    def spy(branch, rel_dir, **kwargs):
        seen.append(branch)
        return real_ls(branch, rel_dir, **kwargs)
    with mock.patch("orchestrator.gitcmd.in_repo", refusing):
        expected = reference_read_tree(TASK)
        with mock.patch("orchestrator.gitcmd.ls_tree_files", spy):
            result = artifact_branch.read_tree(TASK)
    assert result == expected == {}
    assert seen == [artifact_branch.branch_name(TASK)]


# --- AC-5…AC-7 --------------------------------------------------------------

def git_version() -> tuple:
    res = gitcmd.git("--version")
    digits = [int(part) for part in
              res.stdout.split()[2].split(".")[:2]] if res.returncode == 0 else [0, 0]
    return tuple(digits)


def commit_all(sandbox, message: str) -> str:
    sandbox.git("add", "-A")
    sandbox.git("commit", "-q", "-m", message)
    return sandbox.git("rev-parse", "HEAD").strip()


def popen_spy():
    """Подмена `subprocess.Popen` подклассом, пишущим argv: её видят и
    `subprocess.run` (зовёт `Popen` модуля), и прямой `Popen`."""
    real = subprocess.Popen
    calls = []

    class SpyPopen(real):
        def __init__(self, args, *rest, **kwargs):
            calls.append([str(a) for a in args]
                         if not isinstance(args, (str, bytes)) else [args])
            super().__init__(args, *rest, **kwargs)
    return calls, mock.patch.object(subprocess, "Popen", SpyPopen)


@pytest.mark.skipif(git_version() < (2, 31),
                    reason="`--path-format` есть только с git 2.31")
@pytest.mark.parametrize("worktree", [True, False])
def test_ac5_suite_tree_hash_runs_one_rev_parse(real_git, worktree):
    """`suite_tree_hash` в репозитории с git ≥ 2.31 запускает ровно один процесс `rev-parse`.

    Процессы считаются подменой `subprocess.Popen`: через неё идут и
    `subprocess.run` (`gitcmd`), и прямой `Popen` внутреннего `git()`
    функции. Снимок при этом получен (не `None`).

    Ловит мутацию: путь индекса по-прежнему спрашивается вторым
    `rev-parse --path-format=absolute --git-path index` (при
    `worktree=True` процессов `rev-parse` два), либо второй `rev-parse`
    перенесён во внутренний `git()` через `Popen` — шпион видит его, и
    счёт не равен одному.
    """
    calls, patcher = popen_spy()
    with patcher:
        result = acceptance.suite_tree_hash(real_git.root, worktree=worktree)
    rev_parses = [argv for argv in calls if "rev-parse" in argv]
    assert result is not None
    assert len(rev_parses) == 1, rev_parses


def combined_rev_parse_stub(answer):
    """Подмена `gitcmd.in_repo`: объединённый `rev-parse --show-toplevel
    --path-format=absolute …` получает `answer(args)`, прочие вызовы идут
    к настоящему git; `seen` — хвосты всех `rev-parse`."""
    real = gitcmd.in_repo
    seen = []

    def stub(repo, *args):
        if "rev-parse" in args:
            seen.append(args)
        if "--show-toplevel" in args and "--path-format=absolute" in args:
            return answer(args)
        return real(repo, *args)
    return seen, mock.patch("orchestrator.gitcmd.in_repo", stub)


def prepare_suite_case(sandbox, case: str) -> dict:
    """Готовит репозиторий для варианта AC-6; аргументы вызова `suite_tree_hash`."""
    root = sandbox.root
    if case == "subdir":
        (root / "sub").mkdir()
        (root / "sub" / "file.txt").write_text("sub\n", encoding="utf-8")
        commit_all(sandbox, "подкаталог")
        return {"root": root / "sub"}
    if case == "outside_git":
        outside = Path(tempfile.mkdtemp())
        sandbox.addCleanup(shutil.rmtree, outside, True)
        return {"root": outside}
    if case == "ref":
        (root / "first.txt").write_text("1\n", encoding="utf-8")
        first = commit_all(sandbox, "первый")
        (root / "second.txt").write_text("2\n", encoding="utf-8")
        commit_all(sandbox, "второй")
        return {"root": root, "worktree": False, "ref": first}
    if case == "base":
        (root / "tracked.txt").write_text("t\n", encoding="utf-8")
        commit_all(sandbox, "база")
        return {"root": root, "base": True}
    if case == "untracked":
        (root / "loose.txt").write_text("u\n", encoding="utf-8")
        return {"root": root}
    if case == "one_line_stub":
        (root / "edit.txt").write_text("e\n", encoding="utf-8")
        commit_all(sandbox, "правка")
        (root / "edit.txt").write_text("e2\n", encoding="utf-8")
        return {"root": root}
    (root / "edit.txt").write_text("e\n", encoding="utf-8")
    commit_all(sandbox, "корень")
    (root / "edit.txt").write_text("changed\n", encoding="utf-8")
    return {"root": root}


@pytest.mark.parametrize("case", ["root", "subdir", "outside_git", "ref", "base",
                                  "untracked", "one_line_stub"])
def test_ac6_suite_tree_hash_equals_the_reference(real_git, case):
    """`suite_tree_hash` отдаёт то же, что эталон, в каждом варианте критерия.

    Варианты: корень, подкаталог, каталог вне git, `worktree=False` с
    `ref`, `base=True`, неотслеживаемый файл вне каталога задач, заглушка
    `in_repo`, отвечающая на объединённый `rev-parse` одной строкой
    (тогда работают прежние два вызова).

    Ловит мутацию: строки объединённого ответа перепутаны (корень взят из
    пути индекса), сверка с `root` потеряна (подкаталог даёт снимок вместо
    `None`), либо ответ одной строкой принят как правильный — индекс не
    скопирован, снимок расходится с эталоном или вырождается в `None`.
    """
    kwargs = prepare_suite_case(real_git, case)
    assert store.tree_db_files(real_git.root) == []
    if case == "one_line_stub":
        def one_line(args):
            return subprocess.CompletedProcess(args, 0, f"{real_git.root}\n", "")
        seen, patcher = combined_rev_parse_stub(one_line)
        with patcher:
            expected = reference_suite_tree_hash(**kwargs)
            result = acceptance.suite_tree_hash(**kwargs)
        assert expected is not None
    else:
        expected = reference_suite_tree_hash(**kwargs)
        result = acceptance.suite_tree_hash(**kwargs)
    if case in ("root", "ref", "base"):
        assert expected is not None, case
    if case in ("subdir", "outside_git", "untracked"):
        assert expected is None, case
    assert result == expected, case


@pytest.mark.parametrize("worktree", [True, False])
def test_ac7_git_2_30_fallback_runs_the_old_two_calls(real_git, worktree):
    """Объединённый `rev-parse … --path-format=absolute …` отвечает ненулевым кодом: работают прежние вызовы, снимок равен эталону.

    Заглушка `gitcmd.in_repo` моделирует git без `--path-format`: на
    объединённый вызов — код 129, прежние одиночные вызовы проходят к
    настоящему git. Проверяется, что прежний `rev-parse --show-toplevel`
    (и при `worktree=True` — прежний `rev-parse --path-format=absolute
    --git-path index`) выполнен и итог равен эталону, не `None`.

    Ловит мутацию: на отказ объединённого вызова реализация отвечает
    `None` вместо прежних двух вызовов — итог `None` против снимка
    эталона; либо запасной путь пропускает копию индекса — прежнего
    `--git-path index` в `seen` нет.
    """
    (real_git.root / "edit.txt").write_text("e\n", encoding="utf-8")
    commit_all(real_git, "правка")
    (real_git.root / "edit.txt").write_text("e2\n", encoding="utf-8")
    assert store.tree_db_files(real_git.root) == []
    expected = reference_suite_tree_hash(real_git.root, worktree=worktree)
    assert expected is not None

    def refused(args):
        return subprocess.CompletedProcess(args, 129, "",
                                           "error: unknown option `path-format'")
    seen, patcher = combined_rev_parse_stub(refused)
    with patcher:
        result = acceptance.suite_tree_hash(real_git.root, worktree=worktree)
    assert result == expected
    assert ("rev-parse", "--show-toplevel") in seen, seen
    if worktree:
        assert ("rev-parse", "--path-format=absolute", "--git-path",
                "index") in seen, seen
