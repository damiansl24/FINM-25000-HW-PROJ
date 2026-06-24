import os
import requests
import src.exceptions as ex
from dotenv import find_dotenv, load_dotenv
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Load API keys from environment variables

def main() -> tuple[str, str] | None:
    '''
    Load environment variables from nearest ancestor directory 
    (walks up from CWD).

    Includes tests to check existence of the .env file, existence of API keys in the
    file, and whether or not the API keys are valid. 
    '''
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
        print(f'API keys loaded from {env_path}')
    elif not env_path:
        raise ex.envNotFoundError('.env file not found.') # Implement this in exceptions
    
    api_key = os.getenv("ALPACA_API_KEY", "not found.")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "not found.")

    if api_key == 'not found':
        raise ex.keyNotFoundError('alpaca api key not found.')
    elif secret_key == 'not found':
        raise ex.keyNotFoundError('alpaca secret key not found.')
    
    # at this point, we should have the keys loaded. 
    client = StockHistoricalDataClient(api_key, secret_key)
    request_params = StockLatestQuoteRequest(symbol_or_symbols="VOO")

    try:
        client.get_stock_latest_quote(request_params)
    except requests.exceptions.HTTPError as e:
        raise ex.invalidKeyError(f"couldn't validate API keys: alpaca raised {e}.")
    
    return (api_key, secret_key)

if __name__ == "__main__":
    result = main()
    print(result)