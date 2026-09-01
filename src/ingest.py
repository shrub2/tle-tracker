import os
import logging
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from sgp4.api import Satrec

# For debugging
from sys import stdout
from sgp4.conveniences import dump_satrec


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"


def grab_data():
    session = requests.session()

    retries = Retry(
        total = 5,
        backoff_factor = 1,
        status_forcelist = [429, 500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        logger.info("Requesting %s", URL)
        response = session.get(URL)
        logger.info(
            "Got response: %s (%.2fs)",
            response.status_code,
            response.elapsed.total_seconds()
        )
        response.raise_for_status()
    except Exception as e:
        logger.error("Failed to grab data: %s", e)
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filepath = f"data/raw/tle_{timestamp}.txt"
    
    with open(filepath, "w") as f:
        f.write(response.text)
    
    logger.info(
        f"Saved {len(response.text.splitlines()) // 3} objects to {filepath}"
    )


def parse_tle_files(filepath: Path) -> list[tuple[str, Satrec]]:
    files = filepath.iterdir()
    lines = []
    for file in files:
        with file.open('r') as f:
            lines.extend([line.strip() for line in f if line.strip()])

    satellites = []
    for i in range(0, len(lines), 3):
        chunk = lines[i:i + 3]
        if len(chunk) != 3:
            logger.warning(
                "Incomplete TLE record at end of file, skipping: %s", chunk
            )
            break
        name, line1, line2 = chunk
        twoline = Satrec.twoline2rv(line1, line2)
        satellites.append((name, twoline))

    return satellites


def create_database(db_file: str):
    parent = "./database/"
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(parent + db_file)
    conn.close()


def create_table_sql(table_name: str, schema: dict) -> str:
    columns = ", ".join(f"{k} {v}" for k, v in schema.items())
    return f"""CREATE TABLE IF NOT EXISTS {table_name} ({columns});"""


def insert_sql(table_name: str, insert_dict: dict):
    columns = ", ".join(insert_dict.keys())
    placeholders = ", ".join("?" for _ in insert_dict)
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    return sql, tuple(insert_dict.values())


TLE_SCHEMA = {
    "name": "varchar",
    "satnum": "int",
    "class": "varchar",
    "ephtype": "int",
    "elnum": "int",
    "revnum": "int",
}


if __name__ == "__main__":
    # grab_data()
    satellites = parse_tle_files(Path("data/raw"))

    db_file = "tle_tracker.db"
    create_database(db_file)

    table_name = "TLE_tracker"
    try:
        with sqlite3.connect("./database/" + db_file) as conn:
            # Table creation
            conn.execute(create_table_sql(table_name, TLE_SCHEMA))
            # Insert values
            for s in satellites:
                tle_dict = {
                    "name": s[0],
                    "satnum": s[1].satnum,
                    "class": s[1].classification,
                    "ephtype": s[1].ephtype,
                    "elnum": s[1].elnum,
                    "revnum": s[1].revnum,
                }
                sql, params = insert_sql(table_name, tle_dict)
                conn.execute(sql, params)
    except sqlite3.OperationalError as e:
        logger.error("Failed to insert TLE data into DB:", e)

