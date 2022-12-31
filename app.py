from flask import Flask, render_template, session, g, redirect, request
import sqlite3
from werkzeug.security import check_password_hash
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
from datetime import timedelta, datetime

# Initialize flask app
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Path to db
DATABASE = 'tulceana.db'

#Connect and return the db
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

# Closing db after app ends
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur = cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def insert_db(query, args=()):
    cur = get_db().cursor()
    cur = cur.execute(query, args)
    get_db().commit()
    return cur.lastrowid

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/make_booking", methods=['GET', 'POST'])
@login_required
def make_booking():
    
    if request.method == "GET":

        room_type_rows = query_db("SELECT * FROM room_type")

        room_number_rows = query_db("SELECT * FROM rooms")

        return render_template("make_booking.html", room_type_rows=room_type_rows, room_number_rows=room_number_rows)

    else:
        # Insert data into customers database
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        city = request.form.get("city")
        phone = request.form.get("phone")

        customer_id = insert_db("INSERT INTO customers (first_name,last_name, city, phone) VALUES(?, ?, ?, ?)", [first_name, last_name, city, phone])

        number_of_guests = request.form.get("number_of_guests")

        rooms = request.form.getlist("rooms")

        total_booking_price = 0

        for room in rooms:
            check_in_date = request.form.get("check_in_date_" + room)
            check_out_date = request.form.get("check_out_date_" + room)
            check_in_date_obj = datetime.strptime(check_in_date, "%d/%m/%Y")
            check_out_date_obj = datetime.strptime(check_out_date, "%d/%m/%Y")

            difference = (check_out_date_obj - check_in_date_obj).days 

            alldates = []

            for i in range(difference):
                formatted = check_in_date_obj + timedelta(days=i)
                only_date = formatted.strftime("%Y-%m-%d")
                alldates.append(only_date)

            for date in alldates:
                price_row = query_db("SELECT price FROM prices WHERE room_id = ? AND ? >= start_date AND ? <= end_date", [room, date, date])
                total_booking_price = total_booking_price + price_row[0][0]
                
        # Insert booking data into bookings table
        time_of_booking = datetime.now()
        booking_id = insert_db("INSERT INTO bookings (price, customer_id, number_of_guests, time_of_booking ) VALUES (?, ?, ?, ?)", \
                                 [total_booking_price, customer_id, number_of_guests, time_of_booking])

        # Insert booking data into room_line table
        for room in rooms:
            check_in_date = request.form.get("check_in_date_" + room)
            check_out_date = request.form.get("check_out_date_" + room)
            insert_db("INSERT INTO bookings_line (room_id, booking_id, check_in_date, check_out_date) VALUES (?, ?, ?, ?)", [room, booking_id, check_in_date, check_out_date])

        # Redirect user to home page
        return redirect("/confirmation?booking_id=" + str(booking_id))

@app.route("/confirmation")
@login_required
def confirmation():
    booking_id = request.args.get("booking_id")
    return render_template("confirmation.html", booking_id=booking_id)

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("apology.html", message="must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("apology.html", message="must provide password")

        # Query database for username
        rows = query_db("SELECT * FROM admins WHERE user_name = ?", [request.form.get("username")])
        print(rows)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0][2], request.form.get("password")):
            return render_template("apology.html", message="invalid username and/or password")

         # Remember which user has logged in
        session["user_id"] = rows[0][1]
        
        # Redirect user to home page
        return redirect("/make_booking")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

