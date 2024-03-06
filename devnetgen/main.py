import typer

from devnetgen.entities import Entity, VmDto
from devnetgen.executors import CrudExecutor, SummariesExecutor


app = typer.Typer()


@app.command(name='all')
def create_crud(path: str, legacy_controller: bool = False):
    entity = Entity(path)
    executor = CrudExecutor(entity)
    executor.create_all(legacy_controller=legacy_controller)


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


#if __name__ == "__main__":
    #add_summaries('/home/alex/Documents/RiderProjects/SystemsRegistryCore/Domain/Entities/InformationSystems/DatasetHystory.cs')
