from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devnetgen.executors import SourceGeneratorExecutor
    from devnetgen.entities import Namespace


class Constructor:
    __abstract__ = True
    __required_fields__ = ()

    def create_files(self) -> None:
        raise NotImplementedError()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if getattr(cls, '__abstract__', False):
            return

        missing = [field for field in cls.__required_fields__ if not hasattr(cls, field)]
        if missing:
            raise TypeError(f"Class {cls.__name__} is missing required class attributes: {missing}")

    def __init__(self, executor: SourceGeneratorExecutor):
        if self.__class__.__dict__.get('__abstract__', False):
            raise TypeError(f"Class {self.__class__.__name__} is abstract and cannot be instantiated")
        self.entity = executor.entity
        self.executor = executor

    def _create_file_if_not_exists(self, namespace: Namespace, filename: str, content: str) -> None:
        filepath = namespace.path / filename
        if filepath.exists():
            return
        with open(filepath, "w", encoding='utf-8') as file:
            file.write(content)
            self.executor.log_directory(namespace)
