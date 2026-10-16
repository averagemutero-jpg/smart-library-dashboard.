from flask import Flask, request, redirect, url_for, render_template_string, flash
import sqlite3
import re
from datetime import date, timedelta
import os

app = Flask(__name__)
app.secret_key = "change-this-local-library-key"

# Use the same database location as your existing Pydroid 3 project.
DB_NAME = "/storage/emulated/0/library_system.db"


# ---------------- DATABASE ----------------

def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            barcode TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT,
            subject TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS book_details (
            barcode TEXT PRIMARY KEY,
            genre TEXT,
            description TEXT,
            reading_level TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readers (
            reader_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            interests TEXT,
            reading_level TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            reader_id TEXT,
            barcode TEXT,
            rating INTEGER,
            PRIMARY KEY (reader_id, barcode)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reader_id TEXT NOT NULL,
            barcode TEXT NOT NULL,
            borrow_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT
        )
    """)
    conn.commit()
    conn.close()


def next_book_id(conn):
    rows = conn.execute("SELECT barcode FROM books").fetchall()
    highest = 0
    for row in rows:
        match = re.fullmatch(r"LIB(\d+)", row["barcode"] or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return "LIB" + str(highest + 1).zfill(4)


def next_reader_id(conn):
    rows = conn.execute("SELECT reader_id FROM readers").fetchall()
    highest = 0
    for row in rows:
        match = re.fullmatch(r"R(\d+)", row["reader_id"] or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return "R" + str(highest + 1).zfill(4)


# ---------------- PAGE TEMPLATE ----------------

BASE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Library Management System</title>
<style>
:root { --navy:#123c69; --blue:#2563eb; --bg:#f1f5f9; --ink:#172b4d; }
* { box-sizing:border-box; }
body { margin:0; font-family:Arial,sans-serif; background:var(--bg); color:var(--ink); }
header { background:var(--navy); color:white; padding:18px 16px; }
header h1 { margin:0 0 6px; font-size:23px; }
header p { margin:0; opacity:.9; font-size:13px; }
nav { background:#fff; padding:10px 12px; display:flex; flex-wrap:wrap; gap:8px; box-shadow:0 2px 5px #0001; }
nav a { text-decoration:none; color:var(--navy); border:1px solid #dbe3ee; border-radius:8px; padding:9px 11px; font-size:13px; }
main { max-width:1050px; margin:18px auto; padding:0 12px 30px; }
h2 { margin-top:0; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; }
.card, .panel { background:#fff; border-radius:12px; padding:16px; box-shadow:0 2px 8px #172b4d0b; }
.card a { color:inherit; text-decoration:none; display:block; }
.card h3 { margin:0 0 8px; font-size:16px; }
.card p { margin:0; color:#64748b; font-size:13px; }
.num { font-size:30px; font-weight:bold; margin:8px 0; color:var(--blue); }
form { display:grid; gap:12px; }
label { font-size:14px; font-weight:bold; display:grid; gap:6px; }
input, select, textarea { width:100%; padding:11px; border:1px solid #cbd5e1; border-radius:8px; font:inherit; background:#fff; }
textarea { min-height:90px; }
button, .button { display:inline-block; border:0; background:var(--blue); color:white; padding:11px 15px; border-radius:8px; font-weight:bold; text-decoration:none; cursor:pointer; font-size:14px; }
button.danger { background:#b91c1c; }
.actions { display:flex; gap:8px; flex-wrap:wrap; }
.notice { padding:12px; background:#dbeafe; border-radius:8px; margin-bottom:12px; }
.error { background:#fee2e2; }
table { border-collapse:collapse; width:100%; background:white; font-size:13px; }
th, td { padding:10px; text-align:left; border-bottom:1px solid #e2e8f0; vertical-align:top; }
th { background:#eaf0f8; }
.table-wrap { overflow-x:auto; border-radius:10px; }
small, .muted { color:#64748b; }
footer { text-align:center; color:#64748b; padding:20px; font-size:12px; }
@media(max-width:500px) { header h1 {font-size:20px;} nav a {font-size:12px;padding:8px;} th,td {padding:8px;} }
</style>
</head>
<body>
<header><h1>📚 Smart Library Management System</h1><p>Books • Readers • Barcodes • Borrowing • Returns</p></header>
<nav>
<a href="{{ url_for('home') }}">Dashboard</a>
<a href="{{ url_for('register_book') }}">1 Register book</a>
<a href="{{ url_for('books') }}">2 View books</a>
<a href="{{ url_for('edit_book') }}">3 Edit book</a>
<a href="{{ url_for('delete_book') }}">4 Delete book</a>
<a href="{{ url_for('search_book') }}">5 Search</a>
<a href="{{ url_for('recommend') }}">6 AI recommendations</a>
<a href="{{ url_for('scan_lookup') }}">8 Barcode lookup</a>
<a href="{{ url_for('register_reader') }}">9 Readers</a>
<a href="{{ url_for('rate_book') }}">10 Rate book</a>
<a href="{{ url_for('borrow_book') }}">11 Borrow</a>
<a href="{{ url_for('return_book') }}">12 Return</a>
<a href="{{ url_for('borrowed_books') }}">13 Current loans</a>
<a href="{{ url_for('overdue_books') }}">14 Overdue</a>
</nav>
<main>
{% with messages = get_flashed_messages(with_categories=true) %}
{% for category, message in messages %}
<div class="notice {% if category == 'error' %}error{% endif %}">{{ message }}</div>
{% endfor %}
{% endwith %}
{{ content|safe }}
</main>
<footer>Smart Library Management System • Local dashboard</footer>
</body></html>
"""


def page(title, body, **context):
    inner = render_template_string(body, **context)
    return render_template_string(BASE, content=inner, title=title)


def get_book(barcode):
    conn = connect_db()
    row = conn.execute("""
        SELECT b.*, d.genre, d.description, d.reading_level
        FROM books b LEFT JOIN book_details d ON d.barcode=b.barcode
        WHERE b.barcode=?
    """, (barcode,)).fetchone()
    conn.close()
    return row


# ---------------- DASHBOARD / OPTION 7 ----------------

@app.route("/")
def home():
    conn = connect_db()
    books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    readers = conn.execute("SELECT COUNT(*) FROM readers").fetchone()[0]
    loans = conn.execute("SELECT COUNT(*) FROM loans WHERE return_date IS NULL").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE return_date IS NULL AND due_date < ?",
        (date.today().isoformat(),)
    ).fetchone()[0]
    recent = conn.execute("""
        SELECT b.title,b.barcode,r.name,l.borrow_date,l.due_date
        FROM loans l JOIN books b ON b.barcode=l.barcode
        JOIN readers r ON r.reader_id=l.reader_id
        WHERE l.return_date IS NULL ORDER BY l.due_date LIMIT 5
    """).fetchall()
    conn.close()
    body = """
    <h2>Dashboard</h2>
    <div class="grid">
      <div class="card"><p>Registered books</p><div class="num">{{ books }}</div><a class="button" href="{{ url_for('books') }}">View books</a></div>
      <div class="card"><p>Registered readers</p><div class="num">{{ readers }}</div><a class="button" href="{{ url_for('register_reader') }}">Manage readers</a></div>
      <div class="card"><p>Books currently on loan</p><div class="num">{{ loans }}</div><a class="button" href="{{ url_for('borrowed_books') }}">View loans</a></div>
      <div class="card"><p>Overdue books</p><div class="num">{{ overdue }}</div><a class="button" href="{{ url_for('overdue_books') }}">View overdue</a></div>
    </div>
    <div class="panel" style="margin-top:14px"><h3>Currently borrowed books</h3>
    {% if recent %}<div class="table-wrap"><table><tr><th>Book</th><th>Reader</th><th>Borrowed</th><th>Due</th></tr>
    {% for x in recent %}<tr><td>{{ x.title }}<br><small>{{ x.barcode }}</small></td><td>{{ x.name }}</td><td>{{ x.borrow_date }}</td><td>{{ x.due_date }}</td></tr>{% endfor %}
    </table></div>{% else %}<p class="muted">There are no active loans.</p>{% endif %}</div>
    <h2 style="margin-top:22px">All 14 program options</h2>
    <div class="grid">
    {% for n, label, desc, endpoint in options %}
      <div class="card"><a href="{{ url_for(endpoint) }}"><h3>{{ n }}. {{ label }}</h3><p>{{ desc }}</p></a></div>
    {% endfor %}
    </div>
    """
    options = [
        (1,"Register book","Add a book and its details.","register_book"),
        (2,"View all books","See the book catalogue.","books"),
        (3,"Edit book details","Update an existing book.","edit_book"),
        (4,"Delete book","Delete a book if it has no active loan.","delete_book"),
        (5,"Search book","Search by barcode, title, author or subject.","search_book"),
        (6,"AI personalized recommendations","Recommend catalogue books for a reader.","recommend"),
        (7,"Dashboard / Exit","Return to the web dashboard. Stop Flask to exit the server.","home"),
        (8,"Barcode lookup","Enter or scan a barcode to view a book.","scan_lookup"),
        (9,"Register or update reader","Create a reader profile or update interests.","register_reader"),
        (10,"Rate a book","Save a rating from 1 to 5.","rate_book"),
        (11,"Borrow a book","Record a loan and due date.","borrow_book"),
        (12,"Return a book","Record a return and check lateness.","return_book"),
        (13,"View borrowed books","See all active loans.","borrowed_books"),
        (14,"View overdue books","See loans past their due date.","overdue_books"),
    ]
    return page("Dashboard", body, books=books, readers=readers, loans=loans, overdue=overdue, recent=recent, options=options)


# ---------------- OPTION 1: REGISTER BOOK ----------------

@app.route("/books/register", methods=["GET", "POST"])
def register_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        subject = request.form.get("subject", "").strip()
        genre = request.form.get("genre", "").strip()
        description = request.form.get("description", "").strip()
        level = request.form.get("reading_level", "").strip()
        if not title:
            flash("Book title cannot be empty.", "error")
        else:
            conn = connect_db()
            barcode = next_book_id(conn)
            try:
                conn.execute("INSERT INTO books (barcode,title,author,subject) VALUES (?,?,?,?)",
                             (barcode,title,author,subject))
                conn.execute("""INSERT OR REPLACE INTO book_details
                    (barcode,genre,description,reading_level) VALUES (?,?,?,?)""",
                             (barcode,genre,description,level))
                conn.commit()
                flash("Book registered. Barcode: " + barcode)
                conn.close()
                return redirect(url_for("books"))
            except sqlite3.Error as e:
                conn.rollback()
                flash("Could not register book: " + str(e), "error")
            conn.close()
    body = """
    <div class="panel"><h2>1. Register a book</h2>
    <form method="post">
      <label>Book title *<input name="title" required></label>
      <label>Author<input name="author"></label>
      <label>Subject<input name="subject"></label>
      <label>Genre<input name="genre"></label>
      <label>Description<textarea name="description"></textarea></label>
      <label>Reading level<select name="reading_level"><option value="">Select level</option><option>beginner</option><option>intermediate</option><option>advanced</option></select></label>
      <button type="submit">Register book and generate barcode ID</button>
    </form><p class="muted">The system assigns the next LIB barcode ID automatically.</p></div>"""
    return page("Register book", body)


# ---------------- OPTION 2: VIEW BOOKS ----------------

@app.route("/books")
def books():
    term = request.args.get("q", "").strip()
    conn = connect_db()
    if term:
        pat = "%" + term + "%"
        rows = conn.execute("""
            SELECT b.*,d.genre,d.description,d.reading_level FROM books b
            LEFT JOIN book_details d ON d.barcode=b.barcode
            WHERE b.barcode LIKE ? OR b.title LIKE ? OR b.author LIKE ? OR b.subject LIKE ?
            ORDER BY b.title
        """, (pat,pat,pat,pat)).fetchall()
    else:
        rows = conn.execute("""
            SELECT b.*,d.genre,d.description,d.reading_level FROM books b
            LEFT JOIN book_details d ON d.barcode=b.barcode ORDER BY b.title
        """).fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>2. All registered books</h2>
    <form method="get"><label>Filter books<input name="q" value="{{ term }}" placeholder="Title, author, subject or barcode"></label><button>Search catalogue</button></form>
    <p>{{ rows|length }} result(s)</p><div class="table-wrap"><table>
    <tr><th>Barcode</th><th>Book details</th><th>Reading level</th></tr>
    {% for b in rows %}<tr><td><strong>{{ b.barcode }}</strong></td><td><strong>{{ b.title }}</strong><br>Author: {{ b.author or '—' }}<br>Subject: {{ b.subject or '—' }}<br>Genre: {{ b.genre or '—' }}<br>{{ b.description or '' }}</td><td>{{ b.reading_level or '—' }}</td></tr>{% else %}<tr><td colspan="3">No books found.</td></tr>{% endfor %}
    </table></div><p><a class="button" href="{{ url_for('register_book') }}">Register another book</a></p></div>"""
    return page("All books", body, rows=rows, term=term)


# ---------------- OPTION 3: EDIT BOOK ----------------

@app.route("/books/edit", methods=["GET", "POST"])
def edit_book():
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        subject = request.form.get("subject", "").strip()
        genre = request.form.get("genre", "").strip()
        description = request.form.get("description", "").strip()
        level = request.form.get("reading_level", "").strip()
        if not title:
            flash("Book title cannot be empty.", "error")
        else:
            conn = connect_db()
            exists = conn.execute("SELECT barcode FROM books WHERE barcode=?", (barcode,)).fetchone()
            if not exists:
                flash("Book barcode not found.", "error")
            else:
                conn.execute("UPDATE books SET title=?,author=?,subject=? WHERE barcode=?",
                             (title,author,subject,barcode))
                conn.execute("""INSERT OR REPLACE INTO book_details
                    (barcode,genre,description,reading_level) VALUES (?,?,?,?)""",
                             (barcode,genre,description,level))
                conn.commit()
                flash("Book details updated.")
                conn.close()
                return redirect(url_for("books"))
            conn.close()
    barcode = request.args.get("barcode", "").strip()
    book = get_book(barcode) if barcode else None
    body = """
    <div class="panel"><h2>3. Edit book details</h2>
    <form method="get"><label>Find book by barcode<input name="barcode" value="{{ barcode }}" placeholder="e.g. LIB0001" required></label><button>Load book</button></form>
    {% if book %}<hr><form method="post">
      <input type="hidden" name="barcode" value="{{ book.barcode }}">
      <label>Title *<input name="title" value="{{ book.title }}" required></label>
      <label>Author<input name="author" value="{{ book.author or '' }}"></label>
      <label>Subject<input name="subject" value="{{ book.subject or '' }}"></label>
      <label>Genre<input name="genre" value="{{ book.genre or '' }}"></label>
      <label>Description<textarea name="description">{{ book.description or '' }}</textarea></label>
      <label>Reading level<select name="reading_level"><option value="">Select level</option>
      {% for level in ['beginner','intermediate','advanced'] %}<option {% if book.reading_level == level %}selected{% endif %}>{{ level }}</option>{% endfor %}</select></label>
      <button>Save changes</button>
    </form>{% elif barcode %}<p class="notice error">Book not found. Check the barcode.</p>{% endif %}</div>"""
    return page("Edit book", body, book=book, barcode=barcode)


# ---------------- OPTION 4: DELETE BOOK ----------------

@app.route("/books/delete", methods=["GET", "POST"])
def delete_book():
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        confirm = request.form.get("confirm", "")
        conn = connect_db()
        book = conn.execute("SELECT title FROM books WHERE barcode=?", (barcode,)).fetchone()
        active = conn.execute("SELECT loan_id FROM loans WHERE barcode=? AND return_date IS NULL", (barcode,)).fetchone()
        if not book:
            flash("Book not found.", "error")
        elif active:
            flash("This book is currently on loan. Return it before deleting it.", "error")
        elif confirm != "YES":
            flash("Deletion cancelled. Type YES exactly to confirm.", "error")
        else:
            conn.execute("DELETE FROM ratings WHERE barcode=?", (barcode,))
            conn.execute("DELETE FROM book_details WHERE barcode=?", (barcode,))
            conn.execute("DELETE FROM loans WHERE barcode=?", (barcode,))
            conn.execute("DELETE FROM books WHERE barcode=?", (barcode,))
            conn.commit()
            flash("Book deleted: " + book["title"])
        conn.close()
        return redirect(url_for("delete_book"))
    body = """
    <div class="panel"><h2>4. Delete a book</h2><p class="notice error">Deletion is permanent. Books with an active loan cannot be deleted.</p>
    <form method="post">
      <label>Book barcode<input name="barcode" placeholder="e.g. LIB0001" required></label>
      <label>Type YES to confirm deletion<input name="confirm" required></label>
      <button class="danger">Delete book</button>
    </form></div>"""
    return page("Delete book", body)


# ---------------- OPTION 5: SEARCH BOOK ----------------

@app.route("/books/search", methods=["GET", "POST"])
def search_book():
    term = request.values.get("q", "").strip()
    rows = []
    if term:
        conn = connect_db()
        pat = "%" + term + "%"
        rows = conn.execute("""
            SELECT barcode,title,author,subject FROM books
            WHERE barcode LIKE ? OR title LIKE ? OR author LIKE ? OR subject LIKE ?
            ORDER BY title
        """, (pat,pat,pat,pat)).fetchall()
        conn.close()
    body = """
    <div class="panel"><h2>5. Search books</h2><form method="get">
    <label>Barcode, title, author or subject<input name="q" value="{{ term }}" required></label><button>Search</button></form>
    {% if term %}<h3>Results ({{ rows|length }})</h3><div class="table-wrap"><table><tr><th>Barcode</th><th>Title</th><th>Author</th><th>Subject</th></tr>
    {% for b in rows %}<tr><td>{{ b.barcode }}</td><td>{{ b.title }}</td><td>{{ b.author or '—' }}</td><td>{{ b.subject or '—' }}</td></tr>{% else %}<tr><td colspan="4">No matching books found.</td></tr>{% endfor %}</table></div>{% endif %}</div>"""
    return page("Search books", body, term=term, rows=rows)


# ---------------- OPTION 8: BARCODE LOOKUP ----------------

@app.route("/barcode", methods=["GET", "POST"])
def scan_lookup():
    barcode = request.values.get("barcode", "").strip()
    book = get_book(barcode) if barcode else None
    body = """
    <div class="panel"><h2>8. Barcode lookup</h2><p>Use a barcode scanner app, or type/paste the barcode printed under the barcode image.</p>
    <form method="get"><label>Barcode<input name="barcode" value="{{ barcode }}" placeholder="e.g. LIB0001" required autofocus></label><button>Look up book</button></form>
    {% if barcode %}{% if book %}<hr><h3>{{ book.title }}</h3><p><strong>Barcode:</strong> {{ book.barcode }}</p><p><strong>Author:</strong> {{ book.author or '—' }}</p><p><strong>Subject:</strong> {{ book.subject or '—' }}</p><p><strong>Genre:</strong> {{ book.genre or '—' }}</p><p><strong>Description:</strong> {{ book.description or '—' }}</p><p><strong>Reading level:</strong> {{ book.reading_level or '—' }}</p>
    {% else %}<p class="notice error">No book found for barcode {{ barcode }}.</p>{% endif %}{% endif %}</div>"""
    return page("Barcode lookup", body, barcode=barcode, book=book)


# ---------------- OPTION 9: REGISTER READER ----------------

@app.route("/readers/register", methods=["GET", "POST"])
def register_reader():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        interests = request.form.get("interests", "").strip()
        level = request.form.get("reading_level", "").strip()
        if not name:
            flash("Reader's name cannot be empty.", "error")
        else:
            conn = connect_db()
            existing = conn.execute("SELECT reader_id FROM readers WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
            if existing:
                reader_id = existing["reader_id"]
                conn.execute("UPDATE readers SET interests=?,reading_level=? WHERE reader_id=?",
                             (interests,level,reader_id))
                flash("Reader profile updated. Reader ID: " + reader_id)
            else:
                reader_id = next_reader_id(conn)
                conn.execute("INSERT INTO readers (reader_id,name,interests,reading_level) VALUES (?,?,?,?)",
                             (reader_id,name,interests,level))
                flash("Reader registered. Reader ID: " + reader_id)
            conn.commit()
            conn.close()
            return redirect(url_for("readers"))
    conn = connect_db()
    readers = conn.execute("SELECT * FROM readers ORDER BY name").fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>9. Register or update reader</h2>
    <form method="post"><label>Reader's full name *<input name="name" required></label>
    <label>Reading interests<input name="interests" placeholder="e.g. science, history, novels"></label>
    <label>Reading level<select name="reading_level"><option value="">Select level</option><option>beginner</option><option>intermediate</option><option>advanced</option></select></label>
    <button>Save reader</button></form></div>
    <div class="panel" style="margin-top:14px"><h3>Registered readers ({{ readers|length }})</h3><div class="table-wrap"><table><tr><th>Reader ID</th><th>Name</th><th>Interests</th><th>Level</th></tr>
    {% for r in readers %}<tr><td>{{ r.reader_id }}</td><td>{{ r.name }}</td><td>{{ r.interests or '—' }}</td><td>{{ r.reading_level or '—' }}</td></tr>{% else %}<tr><td colspan="4">No readers registered.</td></tr>{% endfor %}</table></div></div>"""
    return page("Readers", body, readers=readers)


# ---------------- OPTION 10: RATE BOOK ----------------

@app.route("/ratings", methods=["GET", "POST"])
def rate_book():
    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        barcode = request.form.get("barcode", "").strip()
        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            rating = 0
        conn = connect_db()
        reader = conn.execute("SELECT reader_id FROM readers WHERE reader_id=?", (reader_id,)).fetchone()
        book = conn.execute("SELECT barcode FROM books WHERE barcode=?", (barcode,)).fetchone()
        if not reader or not book:
            flash("Reader ID or book barcode was not found.", "error")
        elif rating < 1 or rating > 5:
            flash("Rating must be a whole number from 1 to 5.", "error")
        else:
            conn.execute("INSERT OR REPLACE INTO ratings (reader_id,barcode,rating) VALUES (?,?,?)",
                         (reader_id,barcode,rating))
            conn.commit()
            flash("Rating saved.")
            conn.close()
            return redirect(url_for("rate_book"))
        conn.close()
    conn = connect_db()
    readers = conn.execute("SELECT reader_id,name FROM readers ORDER BY name").fetchall()
    books_list = conn.execute("SELECT barcode,title FROM books ORDER BY title").fetchall()
    ratings = conn.execute("""SELECT r.reader_id,rd.name,b.title,b.barcode,r.rating FROM ratings r
        LEFT JOIN readers rd ON rd.reader_id=r.reader_id LEFT JOIN books b ON b.barcode=r.barcode
        ORDER BY rd.name,b.title""").fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>10. Rate a book</h2><form method="post">
    <label>Reader<select name="reader_id" required><option value="">Choose reader</option>{% for r in readers %}<option value="{{ r.reader_id }}">{{ r.reader_id }} — {{ r.name }}</option>{% endfor %}</select></label>
    <label>Book<select name="barcode" required><option value="">Choose book</option>{% for b in books_list %}<option value="{{ b.barcode }}">{{ b.barcode }} — {{ b.title }}</option>{% endfor %}</select></label>
    <label>Rating<select name="rating" required><option value="">Choose rating</option>{% for n in range(1,6) %}<option value="{{ n }}">{{ n }} / 5</option>{% endfor %}</select></label>
    <button>Save rating</button></form></div>
    <div class="panel" style="margin-top:14px"><h3>Saved ratings</h3><div class="table-wrap"><table><tr><th>Reader</th><th>Book</th><th>Rating</th></tr>{% for r in ratings %}<tr><td>{{ r.name or r.reader_id }}</td><td>{{ r.title or r.barcode }}</td><td>{{ r.rating }}/5</td></tr>{% else %}<tr><td colspan="3">No ratings saved.</td></tr>{% endfor %}</table></div></div>"""
    return page("Rate a book", body, readers=readers, books_list=books_list, ratings=ratings)


# ---------------- OPTION 11: BORROW BOOK ----------------

@app.route("/loans/borrow", methods=["GET", "POST"])
def borrow_book():
    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        barcode = request.form.get("barcode", "").strip()
        days_text = request.form.get("days", "14").strip()
        try:
            days = int(days_text or "14")
        except ValueError:
            days = 0
        conn = connect_db()
        reader = conn.execute("SELECT * FROM readers WHERE reader_id=?", (reader_id,)).fetchone()
        book = conn.execute("SELECT * FROM books WHERE barcode=?", (barcode,)).fetchone()
        active = conn.execute("SELECT loan_id FROM loans WHERE barcode=? AND return_date IS NULL", (barcode,)).fetchone()
        if not reader:
            flash("Reader not found. Register the reader first.", "error")
        elif not book:
            flash("Book barcode not found.", "error")
        elif active:
            flash("This book is already borrowed and has not been returned.", "error")
        elif days < 1 or days > 365:
            flash("Loan period must be between 1 and 365 days.", "error")
        else:
            borrowed = date.today()
            due = borrowed + timedelta(days=days)
            conn.execute("INSERT INTO loans (reader_id,barcode,borrow_date,due_date,return_date) VALUES (?,?,?,?,NULL)",
                         (reader_id,barcode,borrowed.isoformat(),due.isoformat()))
            conn.commit()
            flash("Book borrowed successfully. Due date: " + due.isoformat())
            conn.close()
            return redirect(url_for("borrowed_books"))
        conn.close()
    conn = connect_db()
    readers = conn.execute("SELECT reader_id,name FROM readers ORDER BY name").fetchall()
    available = conn.execute("""
        SELECT b.barcode,b.title FROM books b
        WHERE NOT EXISTS (SELECT 1 FROM loans l WHERE l.barcode=b.barcode AND l.return_date IS NULL)
        ORDER BY b.title
    """).fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>11. Borrow a book</h2>
    <form method="post"><label>Reader<select name="reader_id" required><option value="">Choose reader</option>{% for r in readers %}<option value="{{ r.reader_id }}">{{ r.reader_id }} — {{ r.name }}</option>{% endfor %}</select></label>
    <label>Available book<select name="barcode" required><option value="">Choose book</option>{% for b in available %}<option value="{{ b.barcode }}">{{ b.barcode }} — {{ b.title }}</option>{% endfor %}</select></label>
    <label>Loan period in days<input type="number" name="days" min="1" max="365" value="14" required></label><button>Record borrowing</button></form>
    <p class="muted">Only books that are not currently on loan are listed.</p></div>"""
    return page("Borrow a book", body, readers=readers, available=available)


# ---------------- OPTION 12: RETURN BOOK ----------------

@app.route("/loans/return", methods=["GET", "POST"])
def return_book():
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        conn = connect_db()
        loan = conn.execute("""
            SELECT l.*,b.title,r.name FROM loans l
            JOIN books b ON b.barcode=l.barcode JOIN readers r ON r.reader_id=l.reader_id
            WHERE l.barcode=? AND l.return_date IS NULL ORDER BY l.loan_id DESC LIMIT 1
        """, (barcode,)).fetchone()
        if not loan:
            flash("No active loan found for that barcode.", "error")
        else:
            today = date.today()
            due = date.fromisoformat(loan["due_date"])
            conn.execute("UPDATE loans SET return_date=? WHERE loan_id=?",
                         (today.isoformat(),loan["loan_id"]))
            conn.commit()
            if today > due:
                flash("Book returned: " + loan["title"] + ". Returned late by " + str((today-due).days) + " day(s).")
            else:
                flash("Book returned on time: " + loan["title"] + ".")
            conn.close()
            return redirect(url_for("home"))
        conn.close()
    conn = connect_db()
    active = conn.execute("""
        SELECT l.barcode,b.title,r.name,l.due_date FROM loans l
        JOIN books b ON b.barcode=l.barcode JOIN readers r ON r.reader_id=l.reader_id
        WHERE l.return_date IS NULL ORDER BY l.due_date
    """).fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>12. Return a book</h2>
    <form method="post"><label>Barcode of returned book<input name="barcode" required placeholder="e.g. LIB0001"></label><button>Record return</button></form>
    <h3>Active loans</h3><div class="table-wrap"><table><tr><th>Barcode</th><th>Book</th><th>Reader</th><th>Due date</th></tr>{% for l in active %}<tr><td>{{ l.barcode }}</td><td>{{ l.title }}</td><td>{{ l.name }}</td><td>{{ l.due_date }}</td></tr>{% else %}<tr><td colspan="4">No active loans.</td></tr>{% endfor %}</table></div></div>"""
    return page("Return a book", body, active=active)


# ---------------- OPTION 13: VIEW BORROWED BOOKS ----------------

@app.route("/loans")
def borrowed_books():
    conn = connect_db()
    rows = conn.execute("""
        SELECT l.*,b.title,r.name FROM loans l
        JOIN books b ON b.barcode=l.barcode JOIN readers r ON r.reader_id=l.reader_id
        WHERE l.return_date IS NULL ORDER BY l.due_date
    """).fetchall()
    conn.close()
    today = date.today()
    body = """
    <div class="panel"><h2>13. Currently borrowed books</h2><div class="table-wrap"><table>
    <tr><th>Loan ID</th><th>Book</th><th>Reader</th><th>Borrowed</th><th>Due</th><th>Status</th></tr>
    {% for l in rows %}<tr><td>{{ l.loan_id }}</td><td>{{ l.title }}<br><small>{{ l.barcode }}</small></td><td>{{ l.name }}<br><small>{{ l.reader_id }}</small></td><td>{{ l.borrow_date }}</td><td>{{ l.due_date }}</td><td>{% if l.due_date < today %}<strong style="color:#b91c1c">OVERDUE by {{ (today_date - date.fromisoformat(l.due_date)).days }} day(s)</strong>{% else %}On loan{% endif %}</td></tr>{% else %}<tr><td colspan="6">There are no active loans.</td></tr>{% endfor %}
    </table></div><p><a class="button" href="{{ url_for('return_book') }}">Return a book</a></p></div>"""
    # Supply overdue days per row to avoid requiring Python functions in the template.
    prepared = []
    for row in rows:
        d = dict(row)
        d["status"] = ("OVERDUE by " + str((today-date.fromisoformat(row["due_date"])).days) + " day(s)") if row["due_date"] < today.isoformat() else "On loan"
        prepared.append(d)
    body = """
    <div class="panel"><h2>13. Currently borrowed books</h2><div class="table-wrap"><table>
    <tr><th>Loan ID</th><th>Book</th><th>Reader</th><th>Borrowed</th><th>Due</th><th>Status</th></tr>
    {% for l in rows %}<tr><td>{{ l.loan_id }}</td><td>{{ l.title }}<br><small>{{ l.barcode }}</small></td><td>{{ l.name }}<br><small>{{ l.reader_id }}</small></td><td>{{ l.borrow_date }}</td><td>{{ l.due_date }}</td><td>{{ l.status }}</td></tr>{% else %}<tr><td colspan="6">There are no active loans.</td></tr>{% endfor %}
    </table></div><p><a class="button" href="{{ url_for('return_book') }}">Return a book</a></p></div>"""
    return page("Current loans", body, rows=prepared)


# ---------------- OPTION 14: OVERDUE BOOKS ----------------

@app.route("/loans/overdue")
def overdue_books():
    today = date.today()
    conn = connect_db()
    rows = conn.execute("""
        SELECT l.*,b.title,r.name FROM loans l
        JOIN books b ON b.barcode=l.barcode JOIN readers r ON r.reader_id=l.reader_id
        WHERE l.return_date IS NULL AND l.due_date < ? ORDER BY l.due_date
    """, (today.isoformat(),)).fetchall()
    conn.close()
    prepared = []
    for row in rows:
        d = dict(row)
        d["days_overdue"] = (today - date.fromisoformat(row["due_date"])).days
        prepared.append(d)
    body = """
    <div class="panel"><h2>14. Overdue books</h2><div class="table-wrap"><table>
    <tr><th>Book</th><th>Barcode</th><th>Reader</th><th>Borrowed</th><th>Due date</th><th>Days overdue</th></tr>
    {% for l in rows %}<tr><td>{{ l.title }}</td><td>{{ l.barcode }}</td><td>{{ l.name }}<br><small>{{ l.reader_id }}</small></td><td>{{ l.borrow_date }}</td><td>{{ l.due_date }}</td><td><strong style="color:#b91c1c">{{ l.days_overdue }}</strong></td></tr>{% else %}<tr><td colspan="6">No overdue books. Great!</td></tr>{% endfor %}
    </table></div></div>"""
    return page("Overdue books", body, rows=prepared)


# ---------------- OPTION 6: AI RECOMMENDATIONS ----------------

@app.route("/recommendations", methods=["GET", "POST"])
def recommend():
    output = None
    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        goal = request.form.get("goal", "").strip()
        api_key = request.form.get("api_key", "").strip()
        if not api_key:
            flash("Enter your Groq API key to request AI recommendations.", "error")
        else:
            conn = connect_db()
            reader = conn.execute("SELECT * FROM readers WHERE reader_id=?", (reader_id,)).fetchone()
            books_list = conn.execute("""
                SELECT b.barcode,b.title,b.author,b.subject,d.genre,d.description,d.reading_level
                FROM books b LEFT JOIN book_details d ON d.barcode=b.barcode ORDER BY b.title
            """).fetchall()
            ratings = conn.execute("""
                SELECT b.title,r.rating,d.genre FROM ratings r JOIN books b ON b.barcode=r.barcode
                LEFT JOIN book_details d ON d.barcode=b.barcode WHERE r.reader_id=?
            """, (reader_id,)).fetchall()
            conn.close()
            if not reader:
                flash("Reader not found. Register the reader first.", "error")
            elif not books_list:
                flash("No books are registered.", "error")
            else:
                try:
                    from groq import Groq
                    catalogue = "\n\n".join(
                        "Barcode: " + b["barcode"] + "\nTitle: " + b["title"] +
                        "\nAuthor: " + str(b["author"] or "") + "\nSubject: " + str(b["subject"] or "") +
                        "\nGenre: " + str(b["genre"] or "") + "\nDescription: " + str(b["description"] or "") +
                        "\nReading level: " + str(b["reading_level"] or "")
                        for b in books_list
                    )
                    rating_text = "\n".join(r["title"] + ": " + str(r["rating"]) + "/5" for r in ratings) or "No previous ratings."
                    prompt = ("Reader interests: " + str(reader["interests"] or "") +
                              "\nReading level: " + str(reader["reading_level"] or "") +
                              "\nLearning goal: " + goal + "\nPrevious ratings:\n" + rating_text +
                              "\n\nAvailable books:\n" + catalogue +
                              "\n\nRecommend up to three books from this catalogue only. Use exact titles and barcodes. Never invent books or codes. Explain why each recommendation suits the reader.")
                    client = Groq(api_key=api_key, timeout=60)
                    response = client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=[
                            {"role":"system","content":"You are a library assistant. Recommend only books in the supplied catalogue; never invent titles or barcodes."},
                            {"role":"user","content":prompt}
                        ],
                        max_completion_tokens=500
                    )
                    output = response.choices[0].message.content
                except ImportError:
                    flash("The Groq package is missing. In Pydroid 3, install it with pip install groq.", "error")
                except Exception as e:
                    flash("AI recommendation error: " + str(e), "error")
    conn = connect_db()
    readers = conn.execute("SELECT reader_id,name FROM readers ORDER BY name").fetchall()
    conn.close()
    body = """
    <div class="panel"><h2>6. AI personalized recommendations</h2>
    <p>Uses the reader profile, reading goal, ratings and current book catalogue. Your API key is used for this request and is not saved in the library database.</p>
    <form method="post">
      <label>Reader<select name="reader_id" required><option value="">Choose reader</option>{% for r in readers %}<option value="{{ r.reader_id }}">{{ r.reader_id }} — {{ r.name }}</option>{% endfor %}</select></label>
      <label>What would the reader like to learn?<textarea name="goal" required></textarea></label>
      <label>Groq API key<input name="api_key" type="password" autocomplete="off" required></label>
      <button>Get recommendations</button>
    </form>
    {% if output %}<hr><h3>Recommendations</h3><div style="white-space:pre-wrap">{{ output }}</div>{% endif %}
    </div>"""
    return page("AI recommendations", body, readers=readers, output=output)


# ---------------- START ----------------

@app.errorhandler(500)
def internal_error(error):
    return page("Error", '<div class="panel"><h2>Something went wrong</h2><p>Check the Pydroid 3 console for the full error message.</p><p><a class="button" href="/">Return to dashboard</a></p></div>'), 500


if __name__ == "__main__":
    setup_database()
    print("Smart Library dashboard is starting.")
    print("Database:", DB_NAME)
    app.run(host="0.0.0.0", port=5000, debug=False)
