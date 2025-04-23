import re
from pathlib import Path

from devnetgen.entities import Entity, Namespace
from devnetgen.executors import Executor


class SourceGeneratorExecutor(Executor):
    """
    Класс с общими методами для подклассов, генерирующих файлы с исходным кодом

    Attributes:
        entity: сущность для которой создаются элементы
        application_namespace: неполный (базовый) объект Namespace /Application/Work/..
        webui_namespace: неполный (базовый) объект Namespace /Application/Work/..
        command_namespaces: пространства имен команд и запросов
    """
    entity: Entity
    application_namespace: Namespace
    webui_namespace: Namespace
    command_namespaces: dict[str, Namespace]

    def __init__(self, entity: Entity):
        super().__init__(entity.sources_path, entity.solution_name)

        self.entity = entity
        self.command_namespaces = {}

        self._extract_meta()
        self._calculate_namespaces()

    def _calculate_namespaces(self):
        """ Определить базовые директории генерации файлов и соответствующие неполные неймспейсы """
        controller_path = next(self.entity.sources_path.glob('**/Controllers'))

        if match := re.search("^.*References?(.*)", self.entity.namespace.name):
            target = match.group(1)
            application_path, webui_path = self._calculate_paths_references(controller_path, target)
        else:
            target = re.search("^.*Entities(.*)", self.entity.namespace.name).group(1)
            application_path = self.entity.sources_path / 'Application' / 'Work' / target.removeprefix('.').replace('.', '/')
            webui_path = controller_path / 'Work' / target.removeprefix('.').replace('.', '/')

        application_posix = application_path.as_posix()
        namespace_name = self.entity.solution_name + application_posix[application_posix.index('/Application'):].replace('/', '.')
        self.application_namespace = self.entity.get_namespace_obj(namespace_name + f'.{self.entity.pluralized_class_name}')

        webui_posix = webui_path.as_posix()
        prefix = '/WebApi' if self.meta.webapi else '/WebUI'
        namespace_name = self.entity.solution_name + webui_posix[webui_posix.index(prefix):].replace('/', '.')
        self.webui_namespace = self.entity.get_namespace_obj(namespace_name)

    def _calculate_paths_references(self, controller_path: Path, namespace_target: str) -> tuple[Path, Path]:
        application_path_results = tuple((self.entity.sources_path / 'Application').glob('**/References'))
        if len(application_path_results) == 0:
            application_path_results = tuple((self.entity.sources_path / 'Application').glob('**/Reference'))
        application_path = application_path_results[0] / namespace_target.removeprefix('.').replace('.', '/')
        webui_path_results = tuple(controller_path.glob('**/References'))
        if len(application_path_results) == 0:
            webui_path_results = tuple(controller_path.glob('**/Reference'))
        webui_path = webui_path_results[0] / namespace_target.removeprefix('.').replace('.', '/')
        return application_path, webui_path

    def log_directory(self, namespace: Namespace):
        self.changed_files_num += 1
        self.changed_directories.add(namespace.name.replace('.', '/'))
