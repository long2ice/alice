import tortoise

from aerich.ddl.mysql import MysqlDDL
from aerich.ddl.postgres import PostgresDDL
from aerich.ddl.sqlite import SqliteDDL
from aerich.migrate import Migrate
from tests.models import Category, Product, User


def test_create_table():
    ret = Migrate.ddl.create_table(Category)
    if isinstance(Migrate.ddl, MysqlDDL):
        if tortoise.__version__ >= "0.24":
            assert (
                ret
                == """CREATE TABLE IF NOT EXISTS `category` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `slug` VARCHAR(100) NOT NULL,
    `name` VARCHAR(200),
    `title` VARCHAR(20) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `owner_id` INT NOT NULL COMMENT 'User',
    CONSTRAINT `fk_category_user_110d4c63` FOREIGN KEY (`owner_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    FULLTEXT KEY `idx_category_slug_e9bcff` (`slug`)
) CHARACTER SET utf8mb4"""
            )
            return
        assert (
            ret
            == """CREATE TABLE IF NOT EXISTS `category` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `slug` VARCHAR(100) NOT NULL,
    `name` VARCHAR(200),
    `title` VARCHAR(20) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `owner_id` INT NOT NULL COMMENT 'User',
    CONSTRAINT `fk_category_user_110d4c63` FOREIGN KEY (`owner_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE FULLTEXT INDEX `idx_category_slug_e9bcff` ON `category` (`slug`)"""
        )

    elif isinstance(Migrate.ddl, SqliteDDL):
        exists = "IF NOT EXISTS " if tortoise.__version__ >= "0.24" else ""
        assert (
            ret
            == f"""CREATE TABLE IF NOT EXISTS "category" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "slug" VARCHAR(100) NOT NULL,
    "name" VARCHAR(200),
    "title" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "owner_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE /* User */
);
CREATE INDEX {exists}"idx_category_slug_e9bcff" ON "category" ("slug")"""
        )

    elif isinstance(Migrate.ddl, PostgresDDL):
        assert (
            ret
            == """CREATE TABLE IF NOT EXISTS "category" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "slug" VARCHAR(100) NOT NULL,
    "name" VARCHAR(200),
    "title" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "owner_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_category_slug_e9bcff" ON "category" USING HASH ("slug");
COMMENT ON COLUMN "category"."owner_id" IS 'User'"""
        )


def test_drop_table():
    ret = Migrate.ddl.drop_table(Category._meta.db_table)
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "DROP TABLE IF EXISTS `category`"
    else:
        assert ret == 'DROP TABLE IF EXISTS "category"'


def test_add_column():
    ret = Migrate.ddl.add_column(Category, Category._meta.fields_map.get("name").describe(False))
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `category` ADD `name` VARCHAR(200)"
    else:
        assert ret == 'ALTER TABLE "category" ADD "name" VARCHAR(200)'
    # add unique column
    ret = Migrate.ddl.add_column(User, User._meta.fields_map.get("username").describe(False))
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `user` ADD `username` VARCHAR(20) NOT NULL UNIQUE"
    elif isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "user" ADD "username" VARCHAR(20) NOT NULL UNIQUE'
    else:
        assert ret == 'ALTER TABLE "user" ADD "username" VARCHAR(20) NOT NULL'


def test_modify_column():
    if isinstance(Migrate.ddl, SqliteDDL):
        return

    ret0 = Migrate.ddl.modify_column(
        Category, Category._meta.fields_map.get("name").describe(False)
    )
    ret1 = Migrate.ddl.modify_column(User, User._meta.fields_map.get("is_active").describe(False))
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret0 == "ALTER TABLE `category` MODIFY COLUMN `name` VARCHAR(200)"
        assert (
            ret1
            == "ALTER TABLE `user` MODIFY COLUMN `is_active` BOOL NOT NULL COMMENT 'Is Active' DEFAULT 1"
        )
    elif isinstance(Migrate.ddl, PostgresDDL):
        assert (
            ret0
            == 'ALTER TABLE "category" ALTER COLUMN "name" TYPE VARCHAR(200) USING "name"::VARCHAR(200)'
        )

        assert (
            ret1 == 'ALTER TABLE "user" ALTER COLUMN "is_active" TYPE BOOL USING "is_active"::BOOL'
        )


def test_alter_column_default():
    if isinstance(Migrate.ddl, SqliteDDL):
        return
    ret = Migrate.ddl.alter_column_default(User, User._meta.fields_map.get("intro").describe(False))
    if isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "user" ALTER COLUMN "intro" SET DEFAULT \'\''
    elif isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `user` ALTER COLUMN `intro` SET DEFAULT ''"

    ret = Migrate.ddl.alter_column_default(
        Category, Category._meta.fields_map.get("created_at").describe(False)
    )
    if isinstance(Migrate.ddl, PostgresDDL):
        assert (
            ret == 'ALTER TABLE "category" ALTER COLUMN "created_at" SET DEFAULT CURRENT_TIMESTAMP'
        )
    elif isinstance(Migrate.ddl, MysqlDDL):
        assert (
            ret
            == "ALTER TABLE `category` ALTER COLUMN `created_at` SET DEFAULT CURRENT_TIMESTAMP(6)"
        )

    ret = Migrate.ddl.alter_column_default(
        Product, Product._meta.fields_map.get("view_num").describe(False)
    )
    if isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "product" ALTER COLUMN "view_num" SET DEFAULT 0'
    elif isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `product` ALTER COLUMN `view_num` SET DEFAULT 0"


def test_alter_column_null():
    if isinstance(Migrate.ddl, (SqliteDDL, MysqlDDL)):
        return
    ret = Migrate.ddl.alter_column_null(
        Category, Category._meta.fields_map.get("name").describe(False)
    )
    if isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "category" ALTER COLUMN "name" DROP NOT NULL'


def test_set_comment():
    if isinstance(Migrate.ddl, (SqliteDDL, MysqlDDL)):
        return
    ret = Migrate.ddl.set_comment(Category, Category._meta.fields_map.get("name").describe(False))
    assert ret == 'COMMENT ON COLUMN "category"."name" IS NULL'

    ret = Migrate.ddl.set_comment(Category, Category._meta.fields_map.get("owner").describe(False))
    assert ret == 'COMMENT ON COLUMN "category"."owner_id" IS \'User\''


def test_drop_column():
    ret = Migrate.ddl.drop_column(Category, "name")
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `category` DROP COLUMN `name`"
    elif isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "category" DROP COLUMN "name"'


def test_add_index():
    index = Migrate.ddl.add_index(Category, ["name"])
    index_u = Migrate.ddl.add_index(Category, ["name"], True)
    if isinstance(Migrate.ddl, MysqlDDL):
        assert index == "ALTER TABLE `category` ADD INDEX `idx_category_name_8b0cb9` (`name`)"
        assert index_u == "ALTER TABLE `category` ADD UNIQUE INDEX `name` (`name`)"
    elif isinstance(Migrate.ddl, PostgresDDL):
        assert (
            index == 'CREATE INDEX IF NOT EXISTS "idx_category_name_8b0cb9" ON "category" ("name")'
        )
        assert (
            index_u
            == 'CREATE UNIQUE INDEX IF NOT EXISTS "uid_category_name_8b0cb9" ON "category" ("name")'
        )
    else:
        assert index == 'CREATE INDEX "idx_category_name_8b0cb9" ON "category" ("name")'
        assert index_u == 'CREATE UNIQUE INDEX "uid_category_name_8b0cb9" ON "category" ("name")'


def test_drop_index():
    ret = Migrate.ddl.drop_index(Category, ["name"])
    ret_u = Migrate.ddl.drop_index(Category, ["name"], True)
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `category` DROP INDEX `idx_category_name_8b0cb9`"
        assert ret_u == "ALTER TABLE `category` DROP INDEX `name`"
    else:
        assert ret == 'DROP INDEX IF EXISTS "idx_category_name_8b0cb9"'
        assert ret_u == 'DROP INDEX IF EXISTS "uid_category_name_8b0cb9"'


def test_add_fk():
    ret = Migrate.ddl.add_fk(
        Category, Category._meta.fields_map.get("owner").describe(False), User.describe(False)
    )
    if isinstance(Migrate.ddl, MysqlDDL):
        assert (
            ret
            == "ALTER TABLE `category` ADD CONSTRAINT `fk_category_user_110d4c63` FOREIGN KEY (`owner_id`) REFERENCES `user` (`id`) ON DELETE CASCADE"
        )
    else:
        assert (
            ret
            == 'ALTER TABLE "category" ADD CONSTRAINT "fk_category_user_110d4c63" FOREIGN KEY ("owner_id") REFERENCES "user" ("id") ON DELETE CASCADE'
        )


def test_drop_fk():
    ret = Migrate.ddl.drop_fk(
        Category, Category._meta.fields_map.get("owner").describe(False), User.describe(False)
    )
    if isinstance(Migrate.ddl, MysqlDDL):
        assert ret == "ALTER TABLE `category` DROP FOREIGN KEY `fk_category_user_110d4c63`"
    elif isinstance(Migrate.ddl, PostgresDDL):
        assert ret == 'ALTER TABLE "category" DROP CONSTRAINT IF EXISTS "fk_category_user_110d4c63"'
    else:
        assert ret == 'ALTER TABLE "category" DROP FOREIGN KEY "fk_category_user_110d4c63"'
