import typer

import panoctagon.boxing.parse.app as parse
import panoctagon.boxing.scrape.app as scrape

app = typer.Typer()
app.add_typer(scrape.app, name="scrape")
app.add_typer(parse.app, name="parse")

if __name__ == "__main__":
    app()
