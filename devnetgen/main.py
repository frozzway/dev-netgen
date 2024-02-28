import typer

from devnetgen.app import FileClass, Executor


app = typer.Typer()


@app.command()
def main(path: str, legacy_controller: bool = False):
    entity = FileClass(path)
    Executor(entity).create_dto(legacy_controller=legacy_controller)

#if __name__ == "__main__":
    #main('/home/alex/Documents/RiderProjects/MinstroyGasDistributionNetworks/Domain/Entities/Reports/AppealContract.cs')
