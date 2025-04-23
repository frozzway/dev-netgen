from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devnetgen.executors import TestsExecutor
    from devnetgen.entities import Namespace

from devnetgen.constructors.base_crud_constructors import Constructor
from devnetgen.config import env


class TestsConstructor(Constructor):
    template: str
    namespace_prefix: str
    command_suffix: str

    __abstract__ = True

    __required_fields__ = (
        'template', 'namespace_prefix', 'command_suffix'
    )

    @property
    def namespace(self) -> Namespace:
        """Вернуть пространство имени для генерируемых файлов"""
        tests_namespace = self.executor.application_namespace.name.replace('Application', 'Application.IntegrationTests.Tests')
        namespace_string = f'{tests_namespace}.{self.namespace_prefix}'
        return self.entity.get_namespace_obj(namespace_string, for_tests=True)

    def __init__(self, executor: TestsExecutor):
        super().__init__(executor)

    def create_files(self) -> None:
        self.namespace.path.mkdir(parents=True, exist_ok=True)

        template = env.get_template(self.template)
        content = template.render(entity=self.entity,
                                  target_namespace=self.namespace.name,
                                  sieve=self.executor.meta.sieve)
        filename = f"{self.namespace.last_name_part}{self.command_suffix}.cs"
        self._create_file_if_not_exists(self.namespace, filename, content)

        self.executor.add_to_git(self.namespace.path)


class CommandTestsConstructor(TestsConstructor):
    namespace_prefix = 'Commands'
    command_suffix = 'CommandTests'
    __abstract__ = True


class QueryTestsConstructor(TestsConstructor):
    namespace_prefix = 'Queries'
    command_suffix = 'QueryTests'
    __abstract__ = True
