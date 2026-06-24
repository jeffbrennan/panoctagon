import os
import smtplib
import time
from pathlib import Path

from sqlalchemy import text

from dagster import AssetKey, DagsterInstance
from panoctagon.common import get_read_engine, get_secret

STALE_REFRESH_HOURS = 36

os.environ.setdefault("DAGSTER_HOME", str(Path(__file__).parents[1] / "data" / "dagster"))


def hours_since_last_materialization(asset_key: list[str]) -> float | None:
    instance = DagsterInstance.get()
    event = instance.get_latest_materialization_event(AssetKey(asset_key))
    if event is None:
        return None
    return (time.time() - event.timestamp) / 3600


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


def check_freshness() -> None:
    engine = get_read_engine()
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

    hours_since_refresh = hours_since_last_materialization(["ufc_events"])

    issues = []
    if n_upcoming_fights == 0:
        issues.append("STALE: upcoming fights [0 upcoming fights found]")
    if hours_since_refresh is None or hours_since_refresh > STALE_REFRESH_HOURS:
        issues.append(f"STALE: ufc_events [{hours_since_refresh} hours since last refresh]")

    if len(issues) == 0:
        print("data is fresh")
        return

    send_email("<br>".join(issues))


if __name__ == "__main__":
    check_freshness()
