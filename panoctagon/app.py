import typer

import panoctagon.one.one as one
import panoctagon.ufc.app as ufc

app = typer.Typer(pretty_exceptions_enable=False)
app.add_typer(ufc.app, name="ufc")
app.add_typer(one.app, name="one")

if __name__ == "__main__":
    app()
