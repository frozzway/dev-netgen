import typer

from devnetgen.app import EntityClass, Executor, VmDtoClass


app = typer.Typer()


@app.command(name='all')
def create_crud(path: str, legacy_controller: bool = False):
    entity = EntityClass(path)
    executor = Executor(entity)
    executor.create_all(legacy_controller=legacy_controller)


@app.command(name='summary')
def add_summaries(path: str):
    entity = VmDtoClass(path)
    entity.add_properties_summaries()
    entity.add_class_summary()


if __name__ == "__main__":
    create_crud('/home/alex/Documents/RiderProjects/SystemsRegistryCore/Domain/Entities/Reference/DocumentType.cs')
