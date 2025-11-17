# voo_vti_fetcher.py
from tos_api import TOSAPI

tos = TOSAPI()

def get_voo_vti_quotes():
    """
    Requests market data for VOO and VTI through Schwab Trader API.
    """
    symbols = "VOO,VTI"

    # Schwab endpoint for quotes
    endpoint = "markets/quotes"

    try:
        data = tos.get(endpoint, params={"symbols": symbols})
        return data
    except Exception as e:
        print("Error getting VOO/VTI quotes:", e)
        return None