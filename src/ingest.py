import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime, timezone


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
URL = "https://static.geodataviewer.com/datasets/iss-tle.json"


def grab_data():
    session = requests.session()

    retries = Retry(
        total = 5,
        backoff_factor = 1,
        status_forcelist = [429, 500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        response = session.get(URL)
        response.raise_for_status()
    except Exception as e:
        logger.error("Failed to grab data: %s", e)
        return

    if 'application/json' in response.headers.get('content-type', ''):
        resp_text = ""
        for line in response.json().get("satellites"):
            resp_text += f"{line['name']}\n{line['tle1']}\n{line['tle2']}\n"
    else:
        resp_text = response.text
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filepath = f"data/raw/tle_{timestamp}.txt"
    
    with open(filepath, "w") as f:
        f.write(resp_text)
    
    logger.info(
        f"Saved {len(resp_text.splitlines()) // 3} objects to {filepath}"
    )


if __name__ == "__main__":
    grab_data()

