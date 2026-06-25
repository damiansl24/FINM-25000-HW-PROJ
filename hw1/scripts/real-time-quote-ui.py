import sys
sys.path.insert(0,'..')

from src.get_keys import main
from alpaca.data.live import StockDataStream
import streamlit as sl

api_key, secret_key = main() #type: ignore

# Pulled from Alpaca's SDK documentation
wss_client = StockDataStream(api_key, secret_key)

# async handler
async def quote_data_handler(data):
    # quote data will arrive here
    print(data)

wss_client.subscribe_quotes(quote_data_handler, "SPY")

wss_client.run()
