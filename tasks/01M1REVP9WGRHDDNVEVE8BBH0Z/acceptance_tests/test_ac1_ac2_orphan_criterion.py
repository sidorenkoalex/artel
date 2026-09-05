"""AC-1/AC-2 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «AC-1. Ветка
`artifact/<id>` без строки в `state.db` и отсутствующая на origin —
кандидат на удаление (сирота). AC-2. Ветка `artifact/<id>` без строки в
`state.db`, но присутствующая на origin, — НЕ кандидат на удаление.»

Настоящий bare `origin` (см. `_sandbox.py`): расхождение «ветка есть
локально / ветка есть на origin» заглушкой `gitcmd.git`, отвечающей одним
и тем же успехом на любую команду, не изобразить — ровно тот класс
проверки, ради которого критерий вообще существует (SPEC «Контекст»:
прежний критерий полагался ТОЛЬКО на локальную БД и на чужой копии сносил
живые задачи, у которых просто не было локальной строки).

Красен до реализации: `doctor._orphan_artifact_branches` сегодня не
сверяется с origin вовсе (сравнивает только с `store.all_tasks`) — тест
AC-2 обязан покраснеть (ветка на origin без строки БД сегодня уже
считается сиротой), тест AC-1 может остаться зелёным случайно (тот же
исход, что и раньше), но перестаёт быть красным лишь ПОТОМУ, что критерий
ещё не различает два случая — после реализации оба теста проверяют
действительно разное поведение.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, store  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


class Ac1OrphanRequiresAbsenceFromBothTest(ArtifactOriginSandbox):

    def test_ac1_missing_from_db_and_absent_on_origin_is_orphan(self):
        """Ветка `artifact/t777` заведена только локально (не опубликована
        на origin), строки `t777` в БД нет — единственный кандидат.

        Ловит мутацию: критерий орфанности перестал сверяться со
        `state.db` вовсе (считает сиротой любую ветку, которой нет на
        origin, независимо от БД) — тест не различил бы это от
        правильной реализации сам по себе, но следующий тест (AC-2) уже
        отличает; здесь фиксируется положительный случай.
        """
        self.local_only_artifact_branch("t777")

        orphans = doctor._orphan_artifact_branches(store.db())

        self.assertEqual(orphans, ["artifact/t777"])


class Ac2PresentOnOriginIsNotOrphanTest(ArtifactOriginSandbox):

    def test_ac2_missing_from_db_but_present_on_origin_is_not_orphan(self):
        """Ветка `artifact/t888` без строки БД, но опубликована на
        origin, — критерий не должен считать её сиротой, хотя по старому
        (доветочному) критерию «нет строки в БД» она бы туда попала.

        Ловит мутацию: `_orphan_artifact_branches` не сверяется с origin
        вообще (старое поведение, только `state.db`) — тогда
        `artifact/t888` осталась бы в списке кандидатов, хотя она жива
        на origin (SPEC «Контекст»: именно этот случай сегодня сносит
        живые задачи на чужой копии).
        """
        self.push_artifact_branch("t888")

        orphans = doctor._orphan_artifact_branches(store.db())

        self.assertEqual(orphans, [])

    def test_ac2_mixed_candidates_only_the_one_absent_from_origin_survives(self):
        """Одновременно: `t777` — только локально (сирота), `t888` —
        опубликована на origin (не сирота), `t001` — известна БД и не
        опубликована на origin (не сирота по критерию БД). Только
        `t777` — кандидат.

        Ловит мутацию: фильтр по origin применяется ПЕРЕД фильтром по БД
        через `or` вместо `and` (Требование 1 SPEC: «сиротой считается,
        только если ОБА условия верны») — например, реализация, которая
        считает сиротой ветку, отсутствующую в БД ИЛИ отсутствующую на
        origin, вернула бы `t001` тоже (в БД есть, но на origin её нет).
        """
        store.insert_task(store.db(), "T001", "Живая задача", "in_dev",
                          "task/t001-zhivaya-zadacha", config.DEFAULT_TARGET, 25.0)
        self.local_only_artifact_branch("t001")
        self.local_only_artifact_branch("t777")
        self.push_artifact_branch("t888")

        orphans = doctor._orphan_artifact_branches(store.db())

        self.assertEqual(orphans, ["artifact/t777"])


if __name__ == "__main__":
    unittest.main()
