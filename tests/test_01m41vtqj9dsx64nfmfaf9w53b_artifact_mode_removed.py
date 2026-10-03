"""Артефактная ветка без особого статуса в CI: классификатор пуша не
выделяет `artifact/<x>` в отдельный класс, `guard.py` не знает режима
`--artifact-branch`.

Группа: долгоживущий

Красен до реализации: `ci_push_class.classify` ещё отвечает на `artifact/<x>` отдельным правилом (`code=False`, причина «артефактная ветка»), а `guard.py --artifact-branch` печатает сводку «сдано / черновиков / нарушений», понижает нарушения черновика SPEC до предупреждения с кодом 0 и `check_content` принимает `artifact_branch_mode`.

Свойства проверяются только через публичный интерфейс:
`scripts.ci_push_class.classify` (с явным списком изменённых файлов —
без обращения к git и `gh`), `scripts.guard.main()` с подменённым
`sys.argv` (тем же argv, что набирает CI) и `scripts.guard.check_content`.
Имена веток, список изменённых файлов, вид нарушения содержания
черновика SPEC и место ключа в argv выбираются случайно; зерно
печатается и входит в текст провала.

AC-1 покрывает `test_ac1_…`, AC-2 — `test_ac2_…`. Планка провалидирована
временным стабом реализации (все методы зелёные, стаб удалён).
"""
import contextlib
import inspect
import io
import random
import string
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import ci_push_class, guard

FLAG = "--artifact-branch"
ROUNDS = 12


def _seeded() -> tuple[int, random.Random]:
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def _token(rnd: random.Random) -> str:
    kind = rnd.choice(("ulid", "slug", "nested"))
    if kind == "ulid":
        return "".join(rnd.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                       for _ in range(26))
    slug = "-".join("".join(rnd.choice(string.ascii_lowercase)
                            for _ in range(rnd.randint(2, 8)))
                    for _ in range(rnd.randint(1, 3)))
    if kind == "nested":
        return f"{slug}/{rnd.randint(1, 999)}"
    return slug


def _other_branch(rnd: random.Random) -> str:
    prefix = rnd.choice(("task/", "feature/", "fix/", "artifactory/", ""))
    name = prefix + _token(rnd)
    return "x-" + name if name == "main" else name


def _changed_files(rnd: random.Random) -> list[str]:
    pool_docs = ["docs/adr/0021-docs.md", "docs/backlog.md","README.md",
                 "docs/invariants.md"]
    pool_code = ["orchestrator/fsm.py", "scripts/guard.py",
                 "tests/test_guard_zones.py", ".github/workflows/ci.yml"]
    kind = rnd.choice(("docs", "code", "mixed"))
    if kind == "docs":
        return rnd.sample(pool_docs, rnd.randint(1, len(pool_docs)))
    if kind == "code":
        return rnd.sample(pool_code, rnd.randint(1, len(pool_code)))
    return rnd.sample(pool_docs, 1) + rnd.sample(pool_code, 1)


def _sha(rnd: random.Random) -> str:
    return "".join(rnd.choice("0123456789abcdef") for _ in range(40))


class ArtifactBranchPushIsAnOrdinaryBranchTest(unittest.TestCase):
    """AC-1: пуш в `artifact/<x>` классифицируется общим правилом не-`main`
    ветки."""

    def test_ac1_artifact_push_classified_like_any_other_non_main_branch(self):
        """Пуш в `refs/heads/artifact/<x>` и в случайную другую не-`main` ветку.

        Для каждой пары с одними и теми же `before`/`head` и списком
        изменённых файлов исход `classify` (идёт ли job `python`)
        совпадает, а причина для артефактной ветки не называет её
        артефактной.

        Ловит мутацию: класс `artifact/` в `classify` оставлен (ветка
        по-прежнему отвечает `code=False` «артефактная ветка — тесты
        пропущены») или оставлен отдельным правилом с той же причиной —
        исход для `artifact/<x>` разойдётся с исходом для `task/<x>`, либо
        в причине останется слово «артефактная».
        """
        seed, rnd = _seeded()
        for _ in range(ROUNDS):
            before, head = _sha(rnd), _sha(rnd)
            files = _changed_files(rnd)
            art_ref = f"refs/heads/artifact/{_token(rnd)}"
            other_ref = f"refs/heads/{_other_branch(rnd)}"
            art_code, art_reason = ci_push_class.classify(
                "push", art_ref, before, head, list(files))
            other_code, _other_reason = ci_push_class.classify(
                "push", other_ref, before, head, list(files))
            ctx = (f"зерно {seed}: {art_ref} против {other_ref}, "
                   f"файлы {files}, причина {art_reason!r}")
            self.assertEqual(other_code, art_code,
                             f"исход для артефактной ветки отличается от "
                             f"исхода для другой не-main ветки — {ctx}")
            self.assertNotIn("артефакт", art_reason.lower(),
                             f"причина называет артефактную ветку — {ctx}")


_FRONTMATTER = """---
task: {task}
type: spec
author_role: analyst
status: draft
schema_version: {schema}
---

# SPEC: {title}
"""


def _draft_spec_with_content_violation(rnd: random.Random) -> str:
    """Черновик SPEC с исправным заголовочным блоком и нарушением
    содержания: без обязательных секций либо только с частью из них."""
    text = _FRONTMATTER.format(
        task=_token(rnd).replace("/", "-"),
        schema=rnd.randint(1, 5),
        title=" ".join(_token(rnd).replace("/", " ") for _ in range(2)))
    tail = rnd.choice(("", "\n## Контекст\nфикстура\n",
                       "\n## Требования\n1. фикстура\n",
                       "\n## Контекст\nфикстура\n\n## Не входит\n- ничего\n"))
    return text + tail


def _run_guard(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with mock.patch.object(sys, "argv", ["guard.py", *argv]), \
            contextlib.redirect_stdout(out):
        code = guard.main()
    return code, out.getvalue()


class GuardHasNoArtifactBranchModeTest(unittest.TestCase):
    """AC-2: режима `--artifact-branch` у `scripts/guard.py` нет."""

    def test_ac2_flag_does_not_soften_draft_spec_content_violation(self):
        """Черновик SPEC с нарушением содержания, `guard.py` с ключом `--artifact-branch`.

        Ключ ставится перед путём или после него. Вызов даёт код 1, не
        печатает сводку «сдано N / черновиков M / нарушений K» и раздела
        предупреждений черновиков, а каждое нарушение, которое
        `check_content` находит в этом файле, напечатано среди нарушений.

        Ловит мутацию: ключ `--artifact-branch` по-прежнему разбирается в
        `main()` — сводка «сдано … / черновиков …» появляется в выводе,
        нарушения черновика уходят в предупреждения, и код выхода — 0
        вместо 1.
        """
        seed, rnd = _seeded()
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(ROUNDS):
                text = _draft_spec_with_content_violation(rnd)
                path = Path(tmp) / f"case{i}" / "SPEC.md"
                path.parent.mkdir()
                path.write_text(text, encoding="utf-8")
                expected = guard.check_content(str(path), text)
                ctx = f"зерно {seed}, случай {i}"
                self.assertTrue(expected,
                                f"фикстура без нарушения содержания — {ctx}")
                argv = ([FLAG, str(path)] if rnd.random() < 0.5
                        else [str(path), FLAG])
                code, out = _run_guard(argv)
                ctx = f"{ctx}, argv {argv}, вывод:\n{out}"
                self.assertEqual(1, code, f"код выхода не 1 — {ctx}")
                self.assertNotIn("сдано ", out, f"напечатана сводка — {ctx}")
                self.assertNotIn("черновиков", out,
                                 f"напечатана сводка — {ctx}")
                self.assertNotIn("предупреждения (черновики", out,
                                 f"нарушение понижено до предупреждения — {ctx}")
                for err in expected:
                    self.assertIn(err, out,
                                  f"нарушение содержания не напечатано "
                                  f"как ошибка: {err!r} — {ctx}")

    def test_ac2_check_content_has_no_artifact_branch_mode_parameter(self):
        """`check_content` не принимает параметр `artifact_branch_mode`.

        Сигнатура не несёт такого параметра, и вызов с ним по имени
        отказывает `TypeError` — на любом тексте черновика.

        Ловит мутацию: из `main()` ключ убран, а параметр
        `check_content(..., artifact_branch_mode=False)` оставлен — вызов
        с `artifact_branch_mode=True` по-прежнему возвращает урезанный
        список нарушений вместо отказа.
        """
        seed, rnd = _seeded()
        params = inspect.signature(guard.check_content).parameters
        self.assertNotIn("artifact_branch_mode", params, f"зерно {seed}")
        for _ in range(3):
            text = _draft_spec_with_content_violation(rnd)
            with self.assertRaises(TypeError, msg=f"зерно {seed}"):
                guard.check_content("label", text, artifact_branch_mode=True)

    def test_ac2_usage_text_does_not_mention_the_flag(self):
        """`guard.py` без аргументов печатает справку — ключа `--artifact-branch` в ней нет.

        Ловит мутацию: режим убран из кода, но модульный докстринг (его
        `main()` печатает справкой при пустом argv) по-прежнему описывает
        `--artifact-branch` — справка обещает несуществующий ключ.
        """
        code, out = _run_guard([])
        self.assertEqual(1, code, out)
        self.assertTrue(out.strip(), "справка пуста")
        self.assertNotIn(FLAG, out)


if __name__ == "__main__":
    unittest.main()
