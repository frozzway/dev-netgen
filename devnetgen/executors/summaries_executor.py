from itertools import chain
from pathlib import Path

from devnetgen.entities import Entity, VmDto
from devnetgen.executors import Executor


class SummariesExecutor(Executor):
    def __init__(self, entity: Entity):
        super().__init__(entity.sources_path, entity.solution_name)
        self.entity = entity

    def add_summaries(self):
        application_path = self.solution_path / 'Application'
        vm_files = application_path.rglob(f'{self.entity.class_name}Vm.cs')
        dto_files = application_path.rglob(f'{self.entity.class_name}Dto.cs')

        for file_path in chain(vm_files, dto_files):
            file = VmDto(file_path)
            file.add_properties_summaries()
            file.add_class_summary()
            if file.substituted_file_text != file.file_text:
                self._log_file(file_path)

        self._output_data()

    def _log_file(self, path: Path):
        posix_dir = path.as_posix()
        path = posix_dir[posix_dir.index('/Application'):]
        self.changed_files_num += 1
        self.changed_directories.add(path)

    def _output_data(self):
        print(f'Изменено {self.changed_files_num} файлов:')
        for directory in self.changed_directories:
            print(str(directory).removeprefix(self.solution_name))