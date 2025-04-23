import typer

from devnetgen.entities import Entity, VmDto
from devnetgen.executors import CrudExecutor, SummariesExecutor, TestsExecutor

app = typer.Typer()


@app.command(name='crud')
def create_crud(path: str, legacy_controller: bool = False):
    entity = Entity(path)
    executor = CrudExecutor(entity)
    executor.create_crud(legacy_controller=legacy_controller)


@app.command(name='tests')
def create_tests(path: str):
    entity = Entity(path)
    executor = TestsExecutor(entity)
    executor.create_tests()


@app.command(name='summary')
def add_summaries(path: str):
    if path.endswith('Vm.cs') or path.endswith('Dto.cs'):
        entity = VmDto(path)
        entity.add_properties_summaries()
        entity.add_class_summary()
    else:
        entity = Entity(path)
        executor = SummariesExecutor(entity)
        executor.add_summaries()
