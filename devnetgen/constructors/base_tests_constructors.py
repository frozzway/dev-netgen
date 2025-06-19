from __future__ import annotations
from typing import TYPE_CHECKING

from devnetgen.constructors.base_crud_constructors import Constructor
from devnetgen.config import env

if TYPE_CHECKING:
    from devnetgen.executors import TestsExecutor
    from devnetgen.entities import Namespace


class TestsConstructor(Constructor):
    base_template = "tests/TestBase.cs.j2"
    template: str
    namespace_prefix: str
    command_suffix: str
    filename_prefix: str

    __abstract__ = True

    __required_fields__ = (
        'template', 'namespace_prefix', 'command_suffix', 'filename_prefix'
    )

    @property
    def filename_middle_part(self):
        return self.entity.class_name

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
                                  sieve=self.executor.meta.sieve,
                                  **self.executor.command_namespaces)
        filename = f"{self.filename_prefix}{self.filename_middle_part}{self.command_suffix}.cs"
        self._create_file_if_not_exists(self.namespace, filename, content)
        self.executor.add_to_git(self.namespace.path)
        self.create_base()

    def create_base(self) -> None:
        base_namespace_string = self.namespace.name.removesuffix(f".{self.namespace.last_name_part}")
        base_namespace = self.entity.get_namespace_obj(base_namespace_string, for_tests=True)

        template = env.get_template(self.base_template)
        content = template.render(entity=self.entity, target_namespace=base_namespace_string)

        filename = f"{self.entity.class_name}Base.cs"
        self._create_file_if_not_exists(base_namespace, filename, content)
        self.executor.add_to_git(base_namespace.path)


class CommandTestsConstructor(TestsConstructor):
    namespace_prefix = 'Commands'
    command_suffix = 'CommandTests'
    __abstract__ = True


class QueryTestsConstructor(TestsConstructor):
    namespace_prefix = 'Queries'
    command_suffix = 'QueryTests'
    filename_prefix = 'Get'
    __abstract__ = True
