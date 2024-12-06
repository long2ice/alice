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
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new == new

    def test_same_through_with_different_orders(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
            {"name": "members", "through": "users_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new == new[::-1]

    def test_the_same_field_name_order(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new == new

    def test_same_field_name_with_different_orders(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
            {"name": "users", "through": "users_group"},
        ]
        new = [
            {"name": "users", "through": "user_groups"},
            {"name": "admins", "through": "admin_groups"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new == new[::-1]

    def test_drop_one(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old[::-1]
        assert sorted_new == new
        assert sorted_old[0] == new[0]

    def test_add_one(self) -> None:
        old = [
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new == new[::-1]
        assert sorted_old[0] == sorted_new[0]

    def test_drop_some(self) -> None:
        old = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "admins", "through": "admins_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_new == new
        assert sorted_old[0] == old[1] == sorted_new[0]

    def test_add_some(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "staffs", "through": "staffs_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert sorted_new[0] == new[-1] == sorted_old[0]

    def test_some_through_unchanged(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
            {"name": "admins", "through": "admins_group"},
        ]
        new = [
            {"name": "users", "through": "users_group"},
            {"name": "admins_new", "through": "admins_group"},
            {"name": "staffs_new", "through": "staffs_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert [i["through"] for i in sorted_new][: len(old)] == [i["through"] for i in sorted_old]

    def test_some_unchanged_without_drop_or_add(self) -> None:
        old = [
            {"name": "staffs", "through": "staffs_group"},
            {"name": "admins", "through": "admins_group"},
            {"name": "users", "through": "users_group"},
        ]
        new = [
            {"name": "users_new", "through": "users_group"},
            {"name": "admins_new", "through": "admins_group"},
            {"name": "staffs_new", "through": "staffs_group"},
        ]
        sorted_old, sorted_new = reorder_m2m_fields(old, new)
        assert sorted_old == old
        assert [i["through"] for i in sorted_new] == [i["through"] for i in sorted_old]
