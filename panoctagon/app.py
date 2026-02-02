import typer

import panoctagon.api.cli as data
import panoctagon.one.one as one
import panoctagon.ufc.app as ufc

app = typer.Typer(pretty_exceptions_enable=False)
app.add_typer(ufc.app, name="ufc")
app.add_typer(one.app, name="one")
app.add_typer(data.app, name="data")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
) -> None:
    """Start the Panoctagon API server."""
    import uvicorn

    uvicorn.run(
        "panoctagon.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
