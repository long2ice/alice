from aerich.utils import import_py_file, reorder_m2m_fields


def test_import_py_file() -> None:
    m = import_py_file("aerich/utils.py")
    assert getattr(m, "import_py_file", None)


class TestReorderM2M:
    def test_the_same_through_order(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "members", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new == new_backup

    def test_same_through_with_different_orders(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
            {"name": "members", "through": "users_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new == new_backup[::-1]

    def test_the_same_field_name_order(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new == new_backup

    def test_same_field_name_with_different_orders(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
            {"name": "users", "through": "users_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new == new_backup[::-1]

    def test_drop_one(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert new == new_backup
        assert old == old_backup[::-1]
        assert old[0] == new[0]

    def test_add_one(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new == new_backup[::-1]
        assert new[0] == old[0]

    def test_drop_some(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert new == new_backup
        assert old[0] == old_backup[1] == new[0]

    def test_add_some(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        old_backup, new_backup = old[:], new[:]
        reorder_m2m_fields(old, new)
        assert old == old_backup
        assert new[0] == new_backup[-1] == old[0]
