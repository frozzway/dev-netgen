from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devnetgen.executors import CrudExecutor

from devnetgen.constructors.constructor import Constructor
from devnetgen.config import env
from devnetgen.entities import Entity, Namespace, File


class CRUDConstructor(Constructor):
    name: str
    command_template: str
    model_template: str
    namespace_prefix: str
    namespace_identifier: str
    model_suffix: str
    command_suffix: str
    requires_validator: bool = False
    requires_models: bool = False
    IEntity: bool = False
    validator_template = 'Validator.cs.j2'

    __abstract__ = True
    __required_fields__ = (
        'name', 'command_template', 'namespace_identifier', 'namespace_prefix', 'command_suffix', 'model_suffix'
    )

    def __init__(self, executor: CrudExecutor):
        super().__init__(executor)
        if self.requires_models and not hasattr(self.__class__, 'model_template'):
            raise TypeError(f"Class {self.__class__.__name__} is missing a required attribute 'model_template'")

    @property
    def namespace(self) -> Namespace:
        """Вернуть пространство имени для генерируемых файлов"""
        namespace_string = f'{self.executor.application_namespace.name}.{self.namespace_prefix}.{self.name}{self.entity.class_name}'
        return self.entity.get_namespace_obj(namespace_string, for_tests=False)

    def create_files(self) -> None:
        self.namespace.path.mkdir(parents=True, exist_ok=True)

        self._create_command_file()
        if self.requires_models:
            self._create_model_files()
        if self.requires_validator:
            self._create_validator_file()

        self.executor.add_to_git(self.namespace.path)

    def _create_model_files(self) -> None:
        models = self._create_models()
        for model in models:
            filename = f"{model.name}{self.model_suffix}.cs"
            self._create_file_if_not_exists(self.namespace, filename, model.content)

    def _create_command_file(self) -> None:
        template = env.get_template(self.command_template)
        content = template.render(file=self.entity,
                                  target_namespace=self.namespace.name,
                                  sieve=self.executor.meta.sieve,
                                  **self.executor.get_template_vars()['mediator'])
        filename = f"{self.namespace.last_name_part}{self.command_suffix}.cs"
        self._create_file_if_not_exists(self.namespace, filename, content)

    def _create_model(self, entity: Entity) -> File:
        """
        Сформировать vm/dto по шаблону
        :return: объект типа File с наименованием и содержанием vm/dto
        """
        template = env.get_template(self.model_template)
        content = template.render(
            entity=entity,
            target_namespace=self.namespace.name,
            ientity=self.IEntity)
        return File(entity.class_name, content)

    def _create_models(self) -> list[File]:
        """
        Сформировать vm/dto по шаблону для исходной и навигационных сущностей
        :return: список объектов типа File с наименованиями и содержаниями vm/dto
        """
        entities: list[File] = []
        self._create_and_save_all_models(self.entity, entities)
        return entities

    def _create_and_save_all_models(self, entity: Entity, result: list[File]) -> None:
        model = self._create_model(entity)
        result.append(model)
        for child_entity in entity.included_files:
            model = self._create_model(child_entity)
            result.append(model)

    def _create_validator_file(self) -> None:
        """
        Сгенерировать и записать на диск файл валидатора
        """
        filepath = self.namespace.path / f'{self.namespace.last_name_part}CommandValidator.cs'
        if filepath.exists():
            return
        template = env.get_template(self.validator_template)
        output = template.render(
            file=self.entity,
            action=self.name,
            target_namespace=self.namespace.name)
        with open(filepath, "w", encoding='utf-8') as file:
            file.write(output)
            self.executor.log_directory(self.namespace)


class CommandConstructor(CRUDConstructor):
    namespace_prefix = 'Commands'
    model_suffix = 'Dto'
    command_suffix = 'Command'
    __abstract__ = True


class QueryConstructor(CRUDConstructor):
    namespace_prefix = 'Queries'
    model_suffix = 'Vm'
    command_suffix = 'Query'
    model_template = 'VmTemplate.cs.j2'
    name = 'Get'
    requires_models = True
    __abstract__ = True
