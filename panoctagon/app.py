import typer
import panoctagon.ufc.app as ufc
import panoctagon.one.one as one

app = typer.Typer()
app.add_typer(ufc.app, name="ufc")
app.add_typer(one.app, name="one")

if __name__ == "__main__":
    app()
