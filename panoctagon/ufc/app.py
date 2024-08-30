import typer
import panoctagon.ufc.scrape.app as scrape
import panoctagon.ufc.parse.app as parse

app = typer.Typer()
app.add_typer(scrape.app, name="scrape")
app.add_typer(parse.app, name="parse")

if __name__ == "__main__":
    app()
