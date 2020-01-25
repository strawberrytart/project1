import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)
app.secret_key=os.urandom(24)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/result", methods=["POST"]) #Users will be submitting data via POST to this route called /result
def result():
    
    input_info=request.form.get("book").strip()

    if not(input_info):
        message="Please type in something."
        return render_template("error.html", message=message)
    else:
        data=db.execute("SELECT * FROM books WHERE (author ILIKE :info) OR (title ILIKE :info) \
            OR (isbn ILIKE :info)",{"info":'%'+input_info+'%'}).fetchall()
    if not(data):
        print('Empty List')
        return render_template("error.html", message="No such book.")
    return render_template("result.html", result=data)

    """
    if input_isbn:
        print('Received ISBN')
        query1=db.execute("SELECT * FROM books WHERE isbn ILIKE :isbn", \
            {"isbn":'%'+input_isbn+'%'}).fetchall()
        print(query1)
    if input_title:
        print('Received title')
        query2=db.execute("SELECT * FROM books WHERE title ILIKE :title ", \
            {"title":'%'+input_title+'%'}).fetchall()
        print(set(query2))
    if input_author:
        print('Received author', input_author)
        query3=db.execute("SELECT * FROM books WHERE author ILIKE :author ", \
            {"author":'%'+input_author+'%'}).fetchall()
        print(query3)
    """

 

@app.route("/signup", methods=["POST","GET"])
def signup():
    if request.method=="GET":
        return render_template("signup.html")
    else:
        username=request.form.get("username")
        password=request.form.get("password")
        retype_password=request.form.get("retype-password")

        if not(username):
            message="Please enter a username."
            return render_template("error.html", message=message)
        elif password!=retype_password:
            message="Passwords do not match."
            return render_template("error.html", message=message)
        elif not(password):
            message="Please enter a password."
            return render_template("error.html", message=message)
        
        user_object=db.execute("SELECT * FROM users WHERE username=:username", \
            {"username":username}).fetchall()

        if user_object:
            message="Username is taken!"
            return render_template("error.html", message=message)
        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", \
            {"username":username, "password":password})
        db.commit()
        return render_template("success.html", message="Success. You are registered as a user.")

@app.route("/bookpage/<string:isbn>/<int:book_id>", methods=["GET", "POST"])
def bookpage(isbn,book_id):
    if request.method=="GET":
        book=db.execute("SELECT * FROM books WHERE isbn=:isbn",{"isbn":isbn}).fetchone() #ask victor
        if book is None:
            return("No such book")
        review_obj=db.execute("SELECT rating, review, created_at, username FROM reviews JOIN users ON reviews.user_id=users.id WHERE book_id=:book_id",\
            {"book_id":book_id}).fetchall()
        res=requests.get("https://www.goodreads.com/book/review_counts.json",params={"key":"Q5oEURCMm1eCOy1yfhvyw", \
                "isbns": isbn})
        if res.status_code !=200:
            #raise Exception("ERROR: API request unsuccessful.")
            return render_template("books_details.html",book=book,reviews=review_obj)
        goodreads=(res.json())['books']
        print(book)
        return render_template("books_details.html",book=book, goodreads=goodreads, reviews=review_obj)
    else:
        res=request.form
        review=res.get("review")
        rating=res.get("inlineRadioOptions")
        user_id=session["user_id"]
        print(review,rating,book_id)
        print(session["user_id"])

        review_obj=db.execute("SELECT * FROM reviews WHERE (book_id=:book_id) AND (user_id=:user_id)", \
            {"book_id":book_id, "user_id":session["user_id"]}).fetchone()
        print(review_obj)
        if review_obj is None:
            db.execute("INSERT INTO reviews (rating, review, user_id, book_id) VALUES (:rating, :review, :user_id, :book_id)", \
                {"rating":rating, "review":review, "book_id":book_id, "user_id":user_id})
            db.commit()
            print("Successfully added review")
        else:
            return render_template("error.html", message="Users cannot review the same book twice.")
        return redirect(url_for("bookpage", isbn=isbn, book_id=book_id))
        
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method=="POST":
        res=request.form

        username=res.get("username").strip()
        password=res.get("password").strip()

        if not(username):
            return("Please provide username.")

        elif not(password):
            return ("Please provide password.")

        account=db.execute("SELECT * FROM users WHERE username=:username",{"username":username}).fetchone()
        if account is None:
            print("Username not found")
            return render_template("error.html", message="Username not found")

        if account.password !=password:
            print("Password incorrect")
            return render_template("error.html", message="Password incorrect")
        else:
            session["user_id"]=account.id
            session["username"]=username
            print(session["user_id"])
            print("User added to session")
            return redirect(url_for("user"))
    else:
        if "user_id" in session:
            return redirect(url_for("user"))
        return render_template("login.html")

@app.route("/user")
def user():
    if "user_id" in session:
        #account_obj=db.execute("SELECT * FROM users WHERE id=:id",{"id":session["user_id"]}).fetchone()
        #print(account_obj)
        return render_template('index.html')
    else:
        return redirect(url_for("login"))

@app.route("/sign_out")
def sign_out():
    session.pop("user_id",None)
    session.pop("username",None)
    return redirect(url_for("login"))
    
@app.route("/api/<string:isbn>")
def book_api(isbn):
    book=db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchone()
    if not(book):
        return jsonify({"error": "Invalid flight_id"}), 404
    else:
        review_list=db.execute("SELECT * FROM books JOIN reviews ON reviews.book_id=books.id WHERE books.id=:book_id",\
             {"book_id":book.id}).fetchall()
        review_count=0
        score=0
        for book in review_list:
            review_count+=1
            score+=book.rating
        return jsonify({
                "title":book.title,
                "author":book.author,
                "year":book.year,
                "isbn":book.isbn,
                "review_count":review_count,
                "average_score":score/review_count,
        })








