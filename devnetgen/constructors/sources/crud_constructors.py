from devnetgen.entities import Namespace
from devnetgen.constructors.base_crud_constructors import CommandConstructor, QueryConstructor


class CreateConstructor(CommandConstructor):
    """Сборщик команды на создание сущности"""
    name = 'Create'
    command_template = 'CreateCommand.cs.j2'
    model_template = 'CreateDto.cs.j2'
    namespace_identifier = 'create_namespace'
    requires_validator = True
    requires_models = True


class UpdateConstructor(CommandConstructor):
    """Сборщик команды на редактирование сущности"""
    name = 'Update'
    command_template = 'UpdateCommand.cs.j2'
    model_template = 'UpdateDto.cs.j2'
    namespace_identifier = 'update_namespace'
    requires_validator = True
    requires_models = True


class DeleteConstructor(CommandConstructor):
    """Сборщик команды на удаление сущности"""
    name = 'Delete'
    command_template = 'DeleteCommand.cs.j2'
    namespace_identifier = 'delete_namespace'


class GetEntityConstructor(QueryConstructor):
    """Сборщик команды на получение сущности"""
    command_template = 'GetEntityQuery.cs.j2'
    namespace_identifier = 'get_namespace'
    IEntity = True


class GetEntitiesConstructor(QueryConstructor):
    """Сборщик команды на получение списка сущностей"""
    command_template = 'GetEntitiesQuery.cs.j2'
    namespace_identifier = 'get_list_namespace'

    @property
    def namespace(self) -> Namespace:
        """Вернуть пространство имени для генерируемых файлов"""
        namespace_string = f'{self.executor.application_namespace.name}.{self.namespace_prefix}.{self.name}{self.entity.pluralized_class_name}'
        return self.entity.get_namespace_obj(namespace_string)


class GetEntityGridConstructor(QueryConstructor):
    """Сборщик команды на получение таблицы сущностей"""
    command_template = 'GetEntityGridQuery.cs.j2'
    namespace_identifier = 'get_grid_namespace'

    @property
    def namespace(self) -> Namespace:
        """Вернуть пространство имени для генерируемых файлов"""
        namespace_string = f'{self.executor.application_namespace.name}.{self.namespace_prefix}.{self.name}{self.entity.class_name}Grid'
        return self.entity.get_namespace_obj(namespace_string)

