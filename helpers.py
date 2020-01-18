import csv
import urllib.request
import requests
import json

from flask import redirect, render_template, request, session, url_for
from functools import wraps

def apology(top="", bottom=""):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
            ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=escape(top), bottom=escape(bottom))

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def lookup(symbol):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # reject symbol if it contains comma
    if "," in symbol:
        return None

    url = "https://api.worldtradingdata.com/api/v1/stock"
    #symbol="AAPL"
    querystring = {"symbol":symbol,"api_token":"HQtf5CmhNsIyuOBNtxgCdWUwtx79jERTUhfkv5P0HHSEmQNI4t7aCQrWubkq"}

    headers = {
        'User-Agent': "PostmanRuntime/7.19.0",
        'Accept': "*/*",
        'Cache-Control': "no-cache",
        'Postman-Token': "8616d9de-ce47-4a09-9a29-b2be4f4cfe3b,1312e50e-4749-4ffe-9147-d4ba7f38e359",
        'Host': "api.worldtradingdata.com",
        'Accept-Encoding': "gzip, deflate",
        'Connection': "keep-alive",
        'cache-control': "no-cache"
        }

    response = requests.request("GET", url, headers=headers, params=querystring)
    Result=json.loads(response.text)


    return {
        "name":Result["data"][0]["name"],
        "price":Result["data"][0]["price"],
        "symbol":Result["data"][0]["symbol"]
    }
def get_history(symbol,date):

        url = "https://www.alphavantage.co/query"
        date=date
        querystring = {"function":"TIME_SERIES_DAILY","symbol":symbol,"apikey":"8UKO9ZOE8VVTSXLP"}

        headers = {
            'User-Agent': "PostmanRuntime/7.19.0",
            'Accept': "*/*",
            'Cache-Control': "no-cache",
            'Postman-Token': "e77c83dd-3f01-4bbe-9d67-33f5e724a088,8af0a38c-32df-4894-9793-24f88919d78b",
            'Host': "www.alphavantage.co",
            'Accept-Encoding': "gzip, deflate",
            'Connection': "keep-alive",
            'cache-control': "no-cache"
            }

        response = requests.request("GET", url, headers=headers, params=querystring)
        Result=json.loads(response.text)


        return {
            #"Date":Result["Monthly Time Series"] ,
            "Open":Result["Time Series (Daily)"][date]["1. open"],

            "High":Result["Time Series (Daily)"][date]["2. high"],
            "Low":Result["Time Series (Daily)"][date]["3. low"],
            "Close":Result["Time Series (Daily)"][date]["4. close"],
            "Volume":Result["Time Series (Daily)"][date]["5. volume"]
        }

def usd(value):
    """Formats value as USD."""
    return "${:,.2f}".format(value)
