# Aerich
 
[![image](https://img.shields.io/pypi/v/aerich.svg?style=flat)](https://pypi.python.org/pypi/aerich)
[![image](https://img.shields.io/github/license/tortoise/aerich)](https://github.com/tortoise/aerich)
[![image](https://github.com/tortoise/aerich/workflows/pypi/badge.svg)](https://github.com/tortoise/aerich/actions?query=workflow:pypi)
[![image](https://github.com/tortoise/aerich/workflows/ci/badge.svg)](https://github.com/tortoise/aerich/actions?query=workflow:ci)
 
[English](./README.md) | Русский

## Введение
 
Aerich - это инструмент для миграции базы данных для TortoiseORM, который аналогичен Alembic для SQLAlchemy или встроенному решению миграций в Django ORM.
 
## Установка
 
Просто установите из pypi:
 
```shell
pip install aerich
```
 
## Быстрый старт
 
```shell
> aerich -h
 
Usage: aerich [OPTIONS] COMMAND [ARGS]...
 
Options:
  -V, --version      Show the version and exit.
  -c, --config TEXT  Config file.  [default: pyproject.toml]
  --app TEXT         Tortoise-ORM app name.
  -h, --help         Show this message and exit.
 
Commands:
  downgrade  Downgrade to specified version.
  heads      Show current available heads in migrate location.
  history    List all migrate items.
  init       Init config file and generate root migrate location.
  init-db    Generate schema and generate app migrate location.
  inspectdb  Introspects the database tables to standard output as...
  migrate    Generate migrate changes file.
  upgrade    Upgrade to specified version.
```
 
## Использование
 
Сначала вам нужно добавить aerich.models в конфигурацию вашего Tortoise-ORM. Пример:
 
```python
TORTOISE_ORM = {
    "connections": {"default": "mysql://root:123456@127.0.0.1:3306/test"},
    "apps": {
        "models": {
            "models": ["tests.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
```
 
### Инициализация
 
```shell
> aerich init -h
 
Usage: aerich init [OPTIONS]
 
  Init config file and generate root migrate location.
 
Options:
  -t, --tortoise-orm TEXT  Tortoise-ORM config module dict variable, like
                           settings.TORTOISE_ORM.  [required]
  --location TEXT          Migrate store location.  [default: ./migrations]
  -s, --src_folder TEXT    Folder of the source, relative to the project root.
  -h, --help               Show this message and exit.
```
 
Инициализируйте файл конфигурации и задайте местоположение миграций:
 
```shell
> aerich init -t tests.backends.mysql.TORTOISE_ORM
 
Success create migrate location ./migrations
Success write config to pyproject.toml
```
 
### Инициализация базы данных
 
```shell
> aerich init-db
 
Success create app migrate location ./migrations/models
Success generate schema for app "models"
```
 
Если ваше приложение Tortoise-ORM не является приложением по умолчанию с именем models, вы должны указать правильное имя приложения с помощью параметра --app, например: aerich --app other_models init-db.
 
### Обновление моделей и создание миграции
 
```shell
> aerich migrate --name drop_column
 
Success migrate 1_202029051520102929_drop_column.py
```
 
Формат имени файла миграции следующий: `{версия}_{дата_и_время}_{имя|обновление}.py`.
 
Если aerich предполагает, что вы переименовываете столбец, он спросит: 
Переименовать `{старый_столбец} в {новый_столбец} [True]`. Вы можете выбрать `True`,
чтобы переименовать столбец без удаления столбца, или выбрать `False`, чтобы удалить столбец,
а затем создать новый. Обратите внимание, что последний вариант может привести к потере данных.
 
 
### Обновление до последней версии
 
```shell
> aerich upgrade
 
Success upgrade 1_202029051520102929_drop_column.py
```
 
Теперь ваша база данных обновлена до последней версии.
 
### Откат до указанной версии
 
```shell
> aerich downgrade -h
 
Usage: aerich downgrade [OPTIONS]
 
  Downgrade to specified version.
 
Options:
  -v, --version INTEGER  Specified version, default to last.  [default: -1]
  -d, --delete           Delete version files at the same time.  [default:
                         False]
 
  --yes                  Confirm the action without prompting.
  -h, --help             Show this message and exit.
```
 
```shell
> aerich downgrade
 
Success downgrade 1_202029051520102929_drop_column.py
```
 
Теперь ваша база данных откатилась до указанной версии.
 
### Показать историю
 
```shell
> aerich history
 
1_202029051520102929_drop_column.py
```
 
### Чтобы узнать, какие миграции должны быть применены, можно использовать команду:
 
```shell
> aerich heads
 
1_202029051520102929_drop_column.py
```
 
### Осмотр таблиц базы данных для модели TortoiseORM
 
В настоящее время inspectdb поддерживает MySQL, Postgres и SQLite.
 
```shell
Usage: aerich inspectdb [OPTIONS]
 
  Introspects the database tables to standard output as TortoiseORM model.
 
Options:
  -t, --table TEXT  Which tables to inspect.
  -h, --help        Show this message and exit.
```
 
Посмотреть все таблицы и вывести их на консоль:
 
```shell
aerich --app models inspectdb
```
 
Осмотреть указанную таблицу в приложении по умолчанию и перенаправить в models.py:
 
```shell
aerich inspectdb -t user > models.py
```
 
Например, ваша таблица выглядит следующим образом:
 
```sql
CREATE TABLE `test`
(
    `id`       int            NOT NULL AUTO_INCREMENT,
    `decimal`  decimal(10, 2) NOT NULL,
    `date`     date                                    DEFAULT NULL,
    `datetime` datetime       NOT NULL                 DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `time`     time                                    DEFAULT NULL,
    `float`    float                                   DEFAULT NULL,
    `string`   varchar(200) COLLATE utf8mb4_general_ci DEFAULT NULL,
    `tinyint`  tinyint                                 DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `asyncmy_string_index` (`string`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci
```
 
Теперь выполните команду aerich inspectdb -t test, чтобы увидеть сгенерированную модель:
 
```python
from tortoise import Model, fields
 
 
class Test(Model):
    date = fields.DateField(null=True, )
    datetime = fields.DatetimeField(auto_now=True, )
    decimal = fields.DecimalField(max_digits=10, decimal_places=2, )
    float = fields.FloatField(null=True, )
    id = fields.IntField(pk=True, )
    string = fields.CharField(max_length=200, null=True, )
    time = fields.TimeField(null=True, )
    tinyint = fields.BooleanField(null=True, )
```
 
Обратите внимание, что эта команда имеет ограничения и не может автоматически определить некоторые поля, такие как `IntEnumField`, `ForeignKeyField` и другие.
 
### Несколько баз данных
 
```python
tortoise_orm = {
    "connections": {
        "default": expand_db_url(db_url, True),
        "second": expand_db_url(db_url_second, True),
    },
    "apps": {
        "models": {"models": ["tests.models", "aerich.models"], "default_connection": "default"},
        "models_second": {"models": ["tests.models_second"], "default_connection": "second", },
    },
}
```
 
Вам нужно указать `aerich.models` только в одном приложении и должны указывать `--app` при запуске команды `aerich migrate` и т.д.
 
## Восстановление рабочего процесса aerich
 
В некоторых случаях, например, при возникновении проблем после обновления `aerich`, вы не можете запустить `aerich migrate` или `aerich upgrade`. В таком случае вы можете выполнить следующие шаги:
 
1. удалите таблицы `aerich`.
2. удалите директорию `migrations/{app}`.
3. rerun `aerich init-db`.
 
Обратите внимание, что эти действия безопасны, и вы можете использовать их для сброса миграций, если у вас слишком много файлов миграции.
 
## Использование aerich в приложении
 
Вы можете использовать `aerich` вне командной строки, используя класс `Command`.
 
```python
from aerich import Command
 
command = Command(tortoise_config=config, app='models')
await command.init()
await command.migrate('test')
```
 
## Лицензия
 
Этот проект лицензирован в соответствии с лицензией
[Apache-2.0](https://github.com/long2ice/aerich/blob/master/LICENSE) Лицензия.