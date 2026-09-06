import datetime
import os
import smtplib
import time
from pathlib import Path

from sqlalchemy import text

from dagster import AssetKey, DagsterInstance
from panoctagon.common import get_read_engine, get_secret

STALE_REFRESH_HOURS = 36

FRESHNESS_ASSETS = [
    ["ufc_events"],
    ["scrape_fights"],
    ["ufc_fights"],
    ["ufc_fighters"],
    ["bfo_parsed_odds"],
    ["bfo_ufc_link"],
]

os.environ.setdefault("DAGSTER_HOME", str(Path(__file__).parents[1] / "data" / "dagster"))


def last_materialization_ts(asset_key: list[str]) -> float | None:
    instance = DagsterInstance.get()
    event = instance.get_latest_materialization_event(AssetKey(asset_key))
    if event is None:
        return None
    return event.timestamp


def hours_since_last_materialization(asset_key: list[str]) -> float | None:
    ts = last_materialization_ts(asset_key)
    if ts is None:
        return None
    return (time.time() - ts) / 3600


def fmt_hours(hours: float | None) -> str:
    if hours is None:
        return "never materialized"
    return f"{hours:.1f}h ago"


def fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "-"
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


def send_email(body: str) -> None:
    subject = "[ALERT] Panoctagon Data Stale"

    sender = get_secret("BACKEND_EMAIL_FROM")
    password = get_secret("BACKEND_EMAIL_PW")
    recipient = get_secret("BACKEND_EMAIL_LIST")

    headers = [
        f"To: {recipient}",
        f"From: {sender}",
        f"Subject: {subject}",
        "MIME-Version: 1.0",
        "Content-Type: text/html",
    ]

    headers_str = "\r\n".join(headers)
    content = headers_str + "\r\n\r\n" + body
    print(content)

    mail = smtplib.SMTP("smtp.gmail.com", 587)
    mail.ehlo()
    mail.starttls()

    mail.login(sender, password)
    mail.sendmail(from_addr=sender, to_addrs=recipient, msg=content)

    mail.quit()


def build_alert_body(
    issues: list[str],
    asset_rows: list[tuple[str, float | None, float | None]],
    db_snapshot: dict[str, object],
    checked_at: str,
) -> str:
    issue_items = "".join(f"<li>{issue}</li>" for issue in issues)
    asset_items = "".join(
        f"<tr><td>{name}</td><td>{fmt_hours(hours)}</td><td>{fmt_ts(ts)}</td></tr>"
        for name, hours, ts in asset_rows
    )
    snapshot_items = "".join(
        f"<tr><td>{key}</td><td>{value}</td></tr>"
        for key, value in db_snapshot.items()
    )
    return (
        f"<h3>[ALERT] Panoctagon data stale ({checked_at})</h3>"
        f"<ul>{issue_items}</ul>"
        f"<h4>Asset freshness</h4>"
        f"<table border='1' cellpadding='4'>"
        f"<tr><th>asset</th><th>last refresh</th><th>timestamp</th></tr>"
        f"{asset_items}</table>"
        f"<h4>DB snapshot</h4>"
        f"<table border='1' cellpadding='4'>{snapshot_items}</table>"
    )


def check_freshness() -> None:
    checked_at = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    engine = get_read_engine()
    n_upcoming_fights = None
    max_downloaded_ts = None
    max_event_date = None
    n_events = None
    n_fights = None
    for attempt in range(5):
        try:
            with engine.connect() as conn:
                n_upcoming_fights = conn.execute(
                    text(
                        """
                        select count(*) from ufc_fights f
                        join ufc_events e on f.event_uid = e.event_uid
                        where f.fighter1_result is null and e.event_date::date >= current_date
                        """
                    )
                ).scalar()
                max_downloaded_ts = conn.execute(
                    text("select max(downloaded_ts) from ufc_events")
                ).scalar()
                max_event_date = conn.execute(text("select max(event_date) from ufc_events")).scalar()
                n_events = conn.execute(text("select count(*) from ufc_events")).scalar()
                n_fights = conn.execute(text("select count(*) from ufc_fights")).scalar()
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(10)

    hours_since_refresh = hours_since_last_materialization(["ufc_events"])

    issues = []
    if n_upcoming_fights == 0:
        issues.append(
            f"Upcoming fights: 0 found (max downloaded_ts={max_downloaded_ts})"
        )
    if hours_since_refresh is None or hours_since_refresh > STALE_REFRESH_HOURS:
        issues.append(
            f"ufc_events: {fmt_hours(hours_since_refresh)} "
            f"(threshold {STALE_REFRESH_HOURS}h, max downloaded_ts={max_downloaded_ts})"
        )

    if len(issues) == 0:
        print(f"data is fresh [upcoming={n_upcoming_fights}, max downloaded_ts={max_downloaded_ts}]")
        return

    now = time.time()
    asset_rows = []
    for key in FRESHNESS_ASSETS:
        ts = last_materialization_ts(key)
        hours = (now - ts) / 3600 if ts is not None else None
        asset_rows.append((".".join(key), hours, ts))
    db_snapshot = {
        "upcoming fights": n_upcoming_fights,
        "max downloaded_ts": max_downloaded_ts,
        "max event_date": max_event_date,
        "n events": n_events,
        "n fights": n_fights,
    }

    send_email(build_alert_body(issues, asset_rows, db_snapshot, checked_at))


if __name__ == "__main__":
    check_freshness()
