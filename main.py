from time import sleep
from datetime import datetime
from os import getenv

from bs4 import BeautifulSoup
from requests import post, Session
from requests.adapters import HTTPAdapter, Retry
from gspread import service_account


s = Session()

retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])

s.mount("https://", HTTPAdapter(max_retries=retries))


def signal(recipient: str, message: str = "", attachment: str = ""):
    payload = {
        "message": message,
        "number": getenv("SIGNAL_FROM"),
        "recipients": [recipient],
    }

    print(payload)
    if attachment:
        payload["base64_attachments"] = [attachment]

    resp = post(getenv("SIGNAL_API"), json=payload)

    resp.raise_for_status()


def alert(message: str = "", attachment: str = ""):
    signal(getenv("SIGNAL_TO"), message, attachment)


def get_cnn_page(symbol: str):
    return s.get(
        f"https://money.cnn.com/quote/forecast/forecast.html?symb={symbol}",
        timeout=5,
    ).text


def get_symbol_data(symbol):
    source = get_cnn_page(symbol)
    soup = BeautifulSoup(source, "html5lib")

    while not soup:
        sleep(30)
        source = get_cnn_page(symbol)
        soup = BeautifulSoup(source, "html5lib")

    image_link = (
        soup.find("div", attrs={"class": "wsod_chart"}).find("img").get("src")[2:]
    )

    image_desc = soup.find_all("div", attrs={"class": "wsod_twoCol clearfix"})[1].find(
        "p"
    )

    image = s.get("https://" + image_link, timeout=5).content

    while not image:
        sleep(30)
        image = s.get("https://" + image_link, timeout=5).content

    return f"https://{image_link}", image_desc


if __name__ == "__main__":
    sheet = service_account(filename=getenv("GOOGLE_AUTH_JSON", "creds.json")).open(
        getenv("SHEET", "stonks")
    )

    tickers = sheet.worksheet(getenv("SHEET_FROM", "Tickers"))
    data = sheet.worksheet(getenv("SHEET_TO", "Data"))

    data_row = 1
    for symbol in tickers.col_values(1):
        if (not symbol) or (symbol.upper() != symbol):
            continue

        image, image_desc = get_symbol_data(symbol)

        print(f"got {symbol}")

        data.update(
            range_name=f"A{data_row}",
            values=str(datetime.now()),
            value_input_option="USER_ENTERED",
        )
        data.update(range_name=f"B{data_row}", values=symbol)
        data.update(
            range_name=f"C{data_row}",
            values=f'=IMAGE("{image}")',
            value_input_option="USER_ENTERED",
        )
        # data.update(range_name=f"D{data_row}", values=image_desc.get_text())

        print("updated sheet")

        data_row += 1

        sleep(5)

    if message := getenv("NOTIFY"):
        alert(message)
