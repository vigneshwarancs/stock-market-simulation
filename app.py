
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
from datetime import datetime
import time
from redis import Redis
import rq
from celery import Celery, shared_task
from celery.task.control import inspect
from werkzeug.contrib.cache import MemcachedCache

cache = MemcachedCache(['127.0.0.1:11211'])

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    symbol=list()
    share=list()
    price=list()
    total=list()
    # total=[]
    sy = db.execute("SELECT symbol FROM portfolio WHERE id = :id", id= session['user_id'])
    sh = db.execute("SELECT shares FROM portfolio WHERE id = :id", id= session['user_id'])
    pr = db.execute("SELECT price FROM portfolio WHERE id = :id", id= session['user_id'])
    for i in range (len(sy)):
        symbol.append(sy[i]["symbol"].upper())
    for i in range (len(sh)):
        share.append(sh[i]["shares"])
    for i in range (len(pr)):
        price.append(pr[i]["price"])
    # templates=dict(symbols=symbol,shares=share,prices=price)
    for i in range(len(symbol)):
        total.append(price[i]*share[i])
    data = zip(symbol,share,price,total)
    sum = 0.0
    for i in range(len(total)):
        sum+=total[i]
    for i in range(len(total)):
        total[i]=usd(total[i])
    rows = db.execute("SELECT cash FROM users WHERE id=:id", id= session['user_id'])
    # cash = float("{:.2f}".format(rows[0]["cash"]))
    sum+=rows[0]["cash"]
    return render_template("index.html", data=data, sum=usd(sum), cash=usd(rows[0]["cash"]))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    symbol = request.form.get("symbol")
    user_id = session['user_id']

    if request.method == "POST":
        stock = lookup(symbol)
        if stock is None:
            return apology("invalid stock")
        shares = request.form.get("shares")
        if not shares.isdigit() or (int(shares)) % 1 != 0 or (int(shares)) <= 0:
            return apology("invalid shares")
        buy_a_stock.apply_async((user_id, stock, shares, symbol),countdown=15)
        return redirect(url_for("index"))

    else:
        return render_template("buy.html")


@celery.task
def buy_a_stock(user_id, stock, shares, symbol):

    print("Buy Initiated:")
    rows = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)
    if rows[0]["cash"] > float(shares) * float(stock["price"]):
        unique = db.execute("INSERT INTO portfolio (id, symbol, shares, price) VALUES(:id, :symbol, :shares, :price)",
                            id=user_id, symbol=symbol, shares=shares,
                            price=stock["price"])
        db.execute(
            "INSERT INTO history (id, symbol, shares, price, transacted) VALUES(:id, :symbol, :shares, :price, :tran)",
            id=user_id, symbol=symbol, shares=shares, price=stock["price"],
            tran=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        if not unique:
            temp = db.execute("SELECT shares FROM portfolio WHERE id=:id AND symbol=:symbol", id=user_id,
                              symbol=symbol)
            db.execute("UPDATE 'portfolio' SET shares=:shares WHERE id=:id AND symbol=:symbol",
                       shares=temp[0]["shares"] + int(shares), id=user_id,
                       symbol=symbol)
        db.execute("UPDATE 'users' SET cash=:cash WHERE id=:id",
                   cash=(rows[0]["cash"]) - (float(shares) * float(stock["price"])), id=user_id)
    i = inspect()
    print("Scheduled -> ",i.scheduled())
    print("Active ->",i.active())
    print("Completed")

@app.route("/history")
@login_required
def history():
    symbol=list()
    share=list()
    price=list()
    transacted=list()
    # total=[]
    sy = db.execute("SELECT symbol FROM history WHERE id = :id", id= session['user_id'])
    sh = db.execute("SELECT shares FROM history WHERE id = :id", id= session['user_id'])
    pr = db.execute("SELECT price FROM history WHERE id = :id", id= session['user_id'])
    tr = db.execute("SELECT transacted FROM history WHERE id = :id", id= session['user_id'])
    for i in range (len(sy)):
        symbol.append(sy[i]["symbol"].upper())
    for i in range (len(sh)):
        share.append(sh[i]["shares"])
    for i in range (len(pr)):
        price.append(pr[i]["price"])
    for i in range (len(tr)):
        transacted.append(tr[i]["transacted"])
    data = zip(symbol,share,price,transacted)
    return render_template("history.html", data=data)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":
        cresult = cache.get(request.form.get("symbol"))
        print('Value in cache: ',cresult)
        if cresult is None:
            print('Cache Miss')
            result = lookup(request.form.get("symbol"))
            cache.set(result['symbol'], result, timeout=5*60)
        else:
            print('Cache Hit')
            return render_template("quoted.html",name = cresult['name'],symbol = cresult['symbol'], price=cresult['price'])
        if result is None:
            return apology("invalid stock")
        return render_template("quoted.html", name=result["name"], symbol=result["symbol"], price=result["price"])
    else:
      return render_template("quote.html")

@app.route("/quote_history", methods=["GET", "POST"])
@login_required
def quote_history():

    if request.method == "POST":
        try:
            result = get_history(request.form.get("symbol"),request.form.get("date"))
            if result is None:
                return apology("invalid stock")
            if result is None:
                return apology("invalid date")
            return render_template("quoted_get.html", Open=result["Open"],High=result["High"],Low=result["Low"],Close=result["Close"],Volume=result["Volume"])
        except:
            return apology("Invalid date")        
    else:
      return render_template("quote_get.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        if not request.form.get("email"):
            return apology("must provide Email ID")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        elif not request.form.get("password2"):
            return apology("must re-enter password")

        if request.form.get("password")!=request.form.get("password2"):
             return apology("passwords do not match")

        hash = pwd_context.encrypt(request.form.get("password"))

        result = db.execute("INSERT INTO users (username, email, address, hash) VALUES(:username, :email, :address, :hash)", username=request.form.get("username"),email=request.form.get("email"),address=request.form.get("address"), hash=hash)
        if not result:
            return apology("username already exists")

        session["user_id"] = result

        return redirect(url_for("index"))

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        stock = lookup(request.form.get("symbol"))
        if stock is None:
            return apology("invalid stock")
        amount = request.form.get("shares")
        user_id = session['user_id']
        symbol=request.form.get("symbol")
        shares = request.form.get("shares")
        sell_a_stock.apply_async((stock,amount,user_id,symbol,shares),countdown=15)
        return redirect(url_for("index"))

    else:
        return render_template("sell.html")

@celery.task(bind=True)
def sell_a_stock(self,stock,amount,user_id,symbolm,sharesm):
    sy = db.execute("SELECT shares FROM portfolio WHERE id = :id AND symbol=:symbol", id= user_id, symbol=symbolm)
    if not sy:
        return apology("You don't own that stock")
    if not amount.isdigit() or (int(amount))%1!=0 or (int(amount))<=0 or int(amount)>sy[0]["shares"]:
        return apology("invalid shares")
    if (sy[0]["shares"]==int(amount)):
        db.execute("DELETE from 'portfolio' WHERE id = :id AND symbol=:symbol",id= user_id, symbol=symbolm )
    else:
        db.execute("UPDATE 'portfolio' SET shares=:shares WHERE id=:id AND symbol=:symbol", shares=sy[0]["shares"]-int(sharesm), id=user_id, symbol=symbolm)
    db.execute("INSERT INTO history (id, symbol, shares, price, transacted) VALUES(:id, :symbol, :shares, :price, :tran)", id= user_id, symbol=symbolm, shares=-int(sharesm), price=stock["price"], tran=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    profit = float(stock["price"])*int(amount)
    temp = db.execute("SELECT cash FROM users WHERE id=:id",id= user_id)
    db.execute("UPDATE 'users' SET cash=:cash WHERE id=:id", cash=temp[0]["cash"]+profit, id= user_id)
    print('Sell initiated:')
    i = inspect()
    print("Scheduled -> ",i.scheduled())
    print("Active ->",i.active())
    print("Completed")


@app.route("/changepass", methods=["GET", "POST"])
@login_required
def changepass():
    """Change password."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("oldpass"):
            return apology("must provide current password")

        # ensure password was submitted
        elif not request.form.get("newpass"):
            return apology("must provide new password")

        elif not request.form.get("newpass2"):
            return apology("must re-enter new password")

        oldpasscheck = db.execute("SELECT hash FROM users WHERE id = :id", id= session['user_id'])

        if not pwd_context.verify(request.form.get("oldpass"), oldpasscheck[0]["hash"]):
            return apology("that is not your current password")

        if request.form.get("newpass")!=request.form.get("newpass2"):
             return apology("your new passwords do not match")

        hashed = pwd_context.encrypt(request.form.get("newpass"))

        db.execute("UPDATE 'users' SET hash=:hash WHERE id=:id", hash=hashed, id= session['user_id'])

        return redirect(url_for("index"))

    else:
        return render_template("changepass.html")

@app.route("/addCard", methods=["GET","POST"])
@login_required
def addCard():
    if request.method == "POST":
        if not request.form.get("routing"):
            return apology("Can't add a card without routing number")
        if not request.form.get("account"):
            return apology("Can't add a card without accounting number")
        db.execute("INSERT INTO 'bank' (id,route,account,balance) VALUES (:id, :route, :account, :balance)",id= session['user_id'], route=request.form.get("routing"), account=request.form.get("account"), balance=request.form.get("amount"))
        return redirect(url_for("index"))
    else:
        return render_template("addCard.html")

@app.route("/transfer", methods=["GET","POST"])
@login_required
def transfer():
    if request.method == "POST":
        if not request.form.get("routing"):
            return apology("Can't add a card without routing number")
        if not request.form.get("account"):
            return apology("Can't add a card without accounting number")
        ac=db.execute("SELECT * FROM bank WHERE id=:id and route=:route and account=:account",id=session['user_id'], route=request.form.get("routing"), account=request.form.get("account"))
        if not ac:
            return apology("Need to register your account first!!")
        am=db.execute("SELECT cash FROM users WHERE id = :id",id=session['user_id'])
        am=am.copy()
        req=request.form.get('amount')
        req=float(req)
        if float(am[0]['cash'])<req:
            return apology("Insufficient Balance!!")
        bal=db.execute("SELECT balance FROM bank WHERE id=:id and route=:route and account=:account", id=session['user_id'], route=request.form.get("routing"), account=request.form.get("account"))
        db.execute("UPDATE 'bank' SET balance=:balance WHERE id=:id", balance=bal[0]['balance']+float(req), id=session['user_id'])
        db.execute("UPDATE 'users' SET cash=:cash WHERE id=:id", cash=am[0]['cash']-float(req), id=session['user_id'])
        return redirect(url_for("index"))
    else:
        return render_template("transfer.html")
@app.route("/money", methods=["GET","POST"])
@login_required
def money():
    if request.method == "POST":
        if not request.form.get("routing"):
            return apology("Can't add a card without routing number")
        if not request.form.get("account"):
            return apology("Can't add a card without accounting number")
        ac=db.execute("SELECT balance FROM bank WHERE id=:id and route=:route and account=:account",id=session['user_id'], route=request.form.get("routing"), account=request.form.get("account"))
        if not ac:
            return apology("Need to register your account first!!")
        am=db.execute("SELECT cash FROM users WHERE id = :id",id=session['user_id'])
        ac=ac.copy()
        req=request.form.get('amount')
        req=float(req)
        if float(ac[0]['balance'])<req:
            return apology("Insufficient Balance!!")
        bal=db.execute("SELECT balance FROM bank WHERE id=:id and route=:route and account=:account", id=session['user_id'], route=request.form.get("routing"), account=request.form.get("account"))
        db.execute("UPDATE 'bank' SET balance=:balance WHERE id=:id", balance=bal[0]['balance']-float(req), id=session['user_id'])
        db.execute("UPDATE 'users' SET cash=:cash WHERE id=:id", cash=am[0]['cash']+float(req), id=session['user_id'])
        return redirect(url_for("index"))
    else:
        return render_template("money.html")

if __name__== "__main__":
    app.run()

