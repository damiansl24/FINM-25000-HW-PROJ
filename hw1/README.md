# FINM 2500, HW 1

Building a Mini Market Data Terminal using Alpaca

This subdirectory includes the code to create a 
mini market data terminal using Alpaca. It 
authenticates to Alpaca API (which must be provided
to each individual in the .env file in the parent directory)

The get_keys.py file both loads and checks API keys. This accounts
for errors in a faulty APi key, loss of a .env file, and errors 
in not inputting the API keys. 

To load API keys: check README.md in the parent directory.

The data connector module connects to the Alpaca Markets data, 
and contains a function allowing the user to download historical data 
over any time frame. 

The exceptions.py file containts custom exceptions used in diagnosing
the faulty loading of API keys. 

The init py file enables the src to act as a package for usage in the scripts 
directory. 

The historical data view jupyter notebook uses the load_historical_data
function from the data_connector_module, and shows a graph of the OHLVC
data for a 30 day time frame for VOO at a 5 minute resolution. 

Note that the LHD function enables the downloading of any ticker at any minute
resolution, for any time frame. 

The real-time quote UI provides a GUI allowing
a user to type a ticker and display current
bid/ask/last trade price, and updates automatically when
new quotes arrive. 

The src directory contains all functions and programs, while the
scripts directory contains all python executables for this 
assignment. 

Tasks:
1. Data Connector Module -> Damian
2. Historical data viewer -> Damian
3. Real time quote UI