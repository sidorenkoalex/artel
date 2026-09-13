"""Регресс-тест на замечание major REVIEW T048 итерации 2:
`orchestrator.catalog.cmd_new` пересчитывает `branch` от РЕАЛЬНО
выданного `store.next_task_number`, а не только от `store.peek_task_number`
(ранняя проверка коллизии ветки, требование 1) — иначе под гонкой двух
конкурентных `new` (peek видит устаревшее значение счётчика, транзакция
`next_task_number` выдаёт следующее) заведённая задача получает `branch`,
не совпадающий с её фактическим `task_id`.

REVIEW итерации 2 воспроизвёл гонку вручную (Фаза B) и мутационно
подтвердил, что откат правки не роняет ни один тест пакета — этот файл
закрывает тот пробел исполняемой защитой.
"""
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture_new_task_id, fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class PeekTaskNumberRaceTest(TmpRootTest):
    """`ROOT` тоже уводится в песочницу (SPEC T049: холодный старт сканирует
    его для посева счётчика — непропатченный ROOT читал бы реальное дерево
    пульта и его настоящие номера задач, ломая счёт «T006» ниже);
    `templates/` копируется рядом, `cmd_new` продолжает читать настоящий
    `templates/SPEC.md`, только уже из песочницы."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.capture(catalog.cmd_init)

    def test_branch_follows_real_task_id_not_stale_peek(self):
        """SPEC T094, требование 2 СУПЕРСЕДИРУЕТ REVIEW T048 итерации 2:
        id задачи — ULID (`idgen.new_task_id()`), не производная от
        `store.next_task_number`/`peek_task_number` — гонка, которую этот
        тест раньше ловил (branch считался от устаревшего peek, пока
        next_task_number уже выдал следующее значение), структурно
        невозможна: `cmd_new` эти функции для id/branch вообще не
        вызывает. Имя метода сохранено байт-в-байт (прецедент AC-7/T031:
        тестовый метод не исчезает без ADR) — тело проверяет актуальный
        инвариант: branch всегда считается от РЕАЛЬНО возвращённого
        task_id, даже если peek_task_number подделан на заведомо неверное
        значение."""
        conn = store.db()
        # Пять «конкурентных» задач всё ещё двигают legacy-счётчик
        # (требование 6 — контур заморожен, не удалён) — на id/branch
        # ниже это уже не влияет никак.
        for _ in range(5):
            store.next_task_number(conn, config.DEFAULT_TARGET)

        real_peek = store.peek_task_number
        with mock.patch.object(
                store, "peek_task_number",
                side_effect=lambda c, t: real_peek(c, t) - 1):
            out, task_id = capture_new_task_id(catalog.cmd_new, "Задача под гонкой")

        row = store.db().execute(
            "SELECT branch FROM tasks WHERE id=?", (task_id,)).fetchone()
        expected_branch = (
            f"task/{task_id.lower()}-{catalog.slugify('Задача под гонкой')}")
        self.assertEqual(
            row["branch"], expected_branch,
            "branch обязан считаться от реального task_id (ULID) — "
            "подделка peek_task_number не должна на него влиять")

        # A7 (generic-путь заведения, AC-5): `cmd_new` больше не заводит
        # worktree/кодовую ветку сама — SPEC.md коммитится плотницки в
        # артефактную ветку пульта (`artifact_branch.commit_files`,
        # `subprocess.run` напрямую, минуя `gitcmd.git`/фейк выше);
        # плотницкая запись, не отвечающая успехом, обрывает `cmd_new`
        # `sys.exit`, так что успешный вывод — сама по себе проверка,
        # что коммит прошёл (сверить его содержимое через
        # `gitcmd.ls_tree_files` в этой песочнице без настоящего git
        # нельзя — тот же `fake_git`).
        self.assertIn(artifact_branch.branch_name(task_id), out)


if __name__ == "__main__":
    unittest.main()
