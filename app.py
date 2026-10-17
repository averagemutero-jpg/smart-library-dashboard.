
import os
import re
import sqlite3
from datetime import date, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-library-local-key")

# On Render, set DATABASE_PATH to /var/data/library_system.db
# For local use, the database is stored beside this Python file.
DB_NAME = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_system.db")
)


# =========================================================
# DATABASE
# =========================================================

def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup_database():
    folder = os.path.dirname(os.path.abspath(DB_NAME))
    os.makedirs(folder, exist_ok=True)

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
            rating INTEGER NOT NULL,
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


def generate_id(conn, table, column, prefix, digits=4):
    rows = conn.execute(
        f"SELECT {column} FROM {table}"
    ).fetchall()

    highest = 0
    for row in rows:
        match = re.fullmatch(
            re.escape(prefix) + r"(\d+)",
            str(row[column] or "")
        )
        if match:
            highest = max(highest, int(match.group(1)))

    return prefix + str(highest + 1).zfill(digits)


def book_exists(conn, barcode):
    return conn.execute(
        "SELECT 1 FROM books WHERE barcode = ?", (barcode,)
    ).fetchone() is not None


def reader_exists(conn, reader_id):
    return conn.execute(
        "SELECT 1 FROM readers WHERE reader_id = ?", (reader_id,)
    ).fetchone() is not None


def book_is_on_loan(conn, barcode):
    return conn.execute("""
        SELECT 1 FROM loans
        WHERE barcode = ? AND return_date IS NULL
    """, (barcode,)).fetchone() is not None


# =========================================================
# HTML LAYOUT
# =========================================================

BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} | Smart Library Dashboard</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f1f5f9;
    color: #172b4d;
}
header {
    background: #123c69;
    color: white;
    padding: 20px 16px;
}
header h1 { margin: 0 0 6px; font-size: 23px; }
header p { margin: 0; font-size: 13px; }
nav {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
    background: white;
    box-shadow: 0 2px 5px #0001;
}
nav a {
    color: #123c69;
    text-decoration: none;
    border: 1px solid #dbe3ee;
    border-radius: 8px;
    padding: 9px;
    font-size: 13px;
}
main { max-width: 1100px; margin: 20px auto; padding: 0 12px 30px; }
.panel, .card {
    background: white;
    padding: 18px;
    border-radius: 12px;
    box-shadow: 0 2px 8px #172b4d0b;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px;
}
.card a { color: inherit; text-decoration: none; display: block; }
.card h3 { margin: 0 0 8px; font-size: 16px; }
.card p { color: #64748b; font-size: 13px; margin: 0; }
.number { color: #2563eb; font-size: 30px; font-weight: bold; margin: 8px 0; }
form { display: grid; gap: 12px; }
label { display: grid; gap: 6px; font-weight: bold; font-size: 14px; }
input, select, textarea {
    width: 100%;
    padding: 11px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font: inherit;
    background: white;
}
textarea { min-height: 85px; }
button, .button {
    display: inline-block;
    padding: 11px 15px;
    background: #2563eb;
    color: white;
    border: 0;
    border-radius: 8px;
    text-decoration: none;
    font-weight: bold;
    cursor: pointer;
}
.danger { background: #b91c1c; }
.notice { background: #dbeafe; padding: 12px; border-radius: 8px; margin-bottom: 12px; }
.error { background: #fee2e2; }
.table-wrap { overflow-x: auto; background: white; border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }
th { background: #eaf0f8; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.muted { color: #64748b; }
footer { text-align: center; color: #64748b; padding: 20px; font-size: 12px; }
@media(max-width: 500px) {
    header h1 { font-size: 20px; }
    nav a { font-size: 12px; }
    th, td { padding: 8px; }
}
</style>
</head>
<body>
<header>
<h1>📚 Smart Library Management System</h1>
<p>Manage books, readers, borrowing, returns and recommendations</p>
</header>
<nav>
<a href="/">Dashboard</a>
<a href="/books/add">Register Book</a>
<a href="/books">View Books</a>
<a href="/books/edit">Edit Book</a>
<a href="/books/delete">Delete Book</a>
<a href="/books/search">Search Book</a>
<a href="/recommendations">Recommendations</a>
<a href="/barcode">Barcode Lookup</a>
<a href="/readers">Readers</a>
<a href="/ratings">Rate Book</a>
<a href="/borrow">Borrow Book</a>
<a href="/return">Return Book</a>
<a href="/loans">Current Loans</a>
<a href="/overdue">Overdue Books</a>
</nav>
<main>
{% with messages = get_flashed_messages(with_categories=true) %}
{% for category, message in messages %}
<div class="notice {% if category == 'error' %}error{% endif %}">
{{ message }}
</div>
{% endfor %}
{% endwith %}
{{ body|safe }}
</main>
<footer>Smart Library Management System</footer>
</body>
</html>
"""


def page(title, body):
    return render_template_string(BASE, title=title, body=body)


def get_book(conn, barcode):
    return conn.execute("""
        SELECT b.*,
               d.genre,
               d.description,
               d.reading_level
        FROM books b
        LEFT JOIN book_details d ON b.barcode = d.barcode
        WHERE b.barcode = ?
    """, (barcode,)).fetchone()


def book_table(rows):
    if not rows:
        return "<p>No books found.</p>"

    output = """
    <div class="table-wrap"><table>
    <tr><th>Barcode</th><th>Title</th><th>Author</th>
    <th>Subject</th><th>Genre</th></tr>
    """

    for row in rows:
        output += (
            "<tr>"
            f"<td>{row['barcode'] or ''}</td>"
            f"<td>{row['title'] or ''}</td>"
            f"<td>{row['author'] or ''}</td>"
            f"<td>{row['subject'] or ''}</td>"
            f"<td>{row['genre'] or ''}</td>"
            "</tr>"
        )

    output += "</table></div>"
    return output


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def home():
    conn = connect_db()

    books_count = conn.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    readers_count = conn.execute(
        "SELECT COUNT(*) FROM readers"
    ).fetchone()[0]

    loans_count = conn.execute("""
        SELECT COUNT(*) FROM loans WHERE return_date IS NULL
    """).fetchone()[0]

    overdue_count = conn.execute("""
        SELECT COUNT(*) FROM loans
        WHERE return_date IS NULL AND due_date < ?
    """, (date.today().isoformat(),)).fetchone()[0]

    conn.close()

    options = [
        ("1. Register Book", "Add a new book to the library.", "/books/add"),
        ("2. View Books", "See all registered books.", "/books"),
        ("3. Edit Book", "Update existing book details.", "/books/edit"),
        ("4. Delete Book", "Remove a book from the collection.", "/books/delete"),
        ("5. Search Book", "Search by title, author or subject.", "/books/search"),
        ("6. AI-Style Recommendations", "Find books using reader interests and ratings.", "/recommendations"),
        ("7. Dashboard", "View library statistics and main options.", "/"),
        ("8. Barcode Lookup", "Find a book using its barcode.", "/barcode"),
        ("9. Register/Update Reader", "Manage library readers.", "/readers"),
        ("10. Rate Book", "Record a reader's rating.", "/ratings"),
        ("11. Borrow Book", "Record a book loan.", "/borrow"),
        ("12. Return Book", "Record a returned book.", "/return"),
        ("13. Current Loans", "View books that have not been returned.", "/loans"),
        ("14. Overdue Books", "Find loans past their due dates.", "/overdue"),
    ]

    body = f"""
    <div class="grid">
      <div class="card"><h3>Registered Books</h3><div class="number">{books_count}</div></div>
      <div class="card"><h3>Registered Readers</h3><div class="number">{readers_count}</div></div>
      <div class="card"><h3>Current Loans</h3><div class="number">{loans_count}</div></div>
      <div class="card"><h3>Overdue Loans</h3><div class="number">{overdue_count}</div></div>
    </div>
    <h2 style="margin-top:24px">Library Functions</h2>
    <div class="grid">
    """

    for name, description, link in options:
        body += f"""
        <div class="card">
          <a href="{link}">
            <h3>{name}</h3>
            <p>{description}</p>
          </a>
        </div>
        """

    body += "</div>"
    return page("Dashboard", body)


# =========================================================
# 1. REGISTER BOOK
# =========================================================

@app.route("/books/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        subject = request.form.get("subject", "").strip()
        barcode = request.form.get("barcode", "").strip()
        genre = request.form.get("genre", "").strip()
        description = request.form.get("description", "").strip()
        reading_level = request.form.get("reading_level", "").strip()

        if not title:
            flash("Book title is required.", "error")
            return redirect(url_for("add_book"))

        conn = connect_db()
        try:
            if not barcode:
                barcode = generate_id(conn, "books", "barcode", "LIB")

            if book_exists(conn, barcode):
                flash("That barcode already exists.", "error")
                return redirect(url_for("add_book"))

            conn.execute("""
                INSERT INTO books (barcode, title, author, subject)
                VALUES (?, ?, ?, ?)
            """, (barcode, title, author, subject))

            conn.execute("""
                INSERT OR REPLACE INTO book_details
                (barcode, genre, description, reading_level)
                VALUES (?, ?, ?, ?)
            """, (barcode, genre, description, reading_level))

            conn.commit()
            flash(f"Book registered successfully. Barcode: {barcode}")
            return redirect(url_for("view_books"))
        except sqlite3.Error as exc:
            flash(f"Database error: {exc}", "error")
        finally:
            conn.close()

    body = """
    <div class="panel">
    <h2>Register a Book</h2>
    <form method="post">
      <label>Book Title *<input name="title" required></label>
      <label>Author<input name="author"></label>
      <label>Subject<input name="subject"></label>
      <label>Barcode (leave blank to generate automatically)<input name="barcode"></label>
      <label>Genre<input name="genre"></label>
      <label>Description<textarea name="description"></textarea></label>
      <label>Reading Level<input name="reading_level"></label>
      <button type="submit">Register Book</button>
    </form>
    </div>
    """
    return page("Register Book", body)


# =========================================================
# 2. VIEW BOOKS
# =========================================================

@app.route("/books")
def view_books():
    conn = connect_db()
    rows = conn.execute("""
        SELECT b.*, d.genre
        FROM books b
        LEFT JOIN book_details d ON b.barcode = d.barcode
        ORDER BY b.title
    """).fetchall()
    conn.close()

    return page(
        "View Books",
        "<div class='panel'><h2>Registered Books</h2>" +
        book_table(rows) + "</div>"
    )


# =========================================================
# 3. EDIT BOOK
# =========================================================

@app.route("/books/edit", methods=["GET", "POST"])
def edit_book():
    conn = connect_db()

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        subject = request.form.get("subject", "").strip()
        genre = request.form.get("genre", "").strip()
        description = request.form.get("description", "").strip()
        reading_level = request.form.get("reading_level", "").strip()

        if not book_exists(conn, barcode):
            conn.close()
            flash("Book not found.", "error")
            return redirect(url_for("edit_book"))

        if not title:
            conn.close()
            flash("Book title is required.", "error")
            return redirect(url_for("edit_book"))

        conn.execute("""
            UPDATE books
            SET title = ?, author = ?, subject = ?
            WHERE barcode = ?
        """, (title, author, subject, barcode))

        conn.execute("""
            INSERT OR REPLACE INTO book_details
            (barcode, genre, description, reading_level)
            VALUES (?, ?, ?, ?)
        """, (barcode, genre, description, reading_level))

        conn.commit()
        conn.close()
        flash("Book details updated successfully.")
        return redirect(url_for("view_books"))

    barcode = request.args.get("barcode", "").strip()
    book = get_book(conn, barcode) if barcode else None
    conn.close()

    if book:
        body = f"""
        <div class="panel"><h2>Edit Book</h2>
        <form method="post">
        <label>Barcode<input name="barcode" value="{book['barcode']}" readonly></label>
        <label>Title<input name="title" value="{book['title'] or ''}" required></label>
        <label>Author<input name="author" value="{book['author'] or ''}"></label>
        <label>Subject<input name="subject" value="{book['subject'] or ''}"></label>
        <label>Genre<input name="genre" value="{book['genre'] or ''}"></label>
        <label>Description<textarea name="description">{book['description'] or ''}</textarea></label>
        <label>Reading Level<input name="reading_level" value="{book['reading_level'] or ''}"></label>
        <button type="submit">Save Changes</button>
        </form></div>
        """
    else:
        body = """
        <div class="panel"><h2>Edit Book</h2>
        <form method="get">
        <label>Enter book barcode<input name="barcode" required></label>
        <button type="submit">Find Book</button>
        </form>
        </div>
        """

    return page("Edit Book", body)


# =========================================================
# 4. DELETE BOOK
# =========================================================

@app.route("/books/delete", methods=["GET", "POST"])
def delete_book():
    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        conn = connect_db()

        if not book_exists(conn, barcode):
            conn.close()
            flash("Book not found.", "error")
            return redirect(url_for("delete_book"))

        if book_is_on_loan(conn, barcode):
            conn.close()
            flash("This book is currently on loan. Record its return before deleting it.", "error")
            return redirect(url_for("delete_book"))

        conn.execute("DELETE FROM ratings WHERE barcode = ?", (barcode,))
        conn.execute("DELETE FROM book_details WHERE barcode = ?", (barcode,))
        conn.execute("DELETE FROM books WHERE barcode = ?", (barcode,))
        conn.commit()
        conn.close()

        flash("Book deleted successfully.")
        return redirect(url_for("view_books"))

    body = """
    <div class="panel"><h2>Delete Book</h2>
    <form method="post" onsubmit="return confirm('Are you sure you want to delete this book?');">
      <label>Book Barcode<input name="barcode" required></label>
      <button class="danger" type="submit">Delete Book</button>
    </form></div>
    """
    return page("Delete Book", body)


# =========================================================
# 5. SEARCH BOOK
# =========================================================

@app.route("/books/search", methods=["GET", "POST"])
def search_book():
    rows = []

    if request.method == "POST":
        term = request.form.get("term", "").strip()
        conn = connect_db()
        like_term = "%" + term + "%"

        rows = conn.execute("""
            SELECT b.*, d.genre
            FROM books b
            LEFT JOIN book_details d ON b.barcode = d.barcode
            WHERE b.title LIKE ?
               OR b.author LIKE ?
               OR b.subject LIKE ?
               OR b.barcode LIKE ?
               OR d.genre LIKE ?
            ORDER BY b.title
        """, (like_term, like_term, like_term, like_term, like_term)).fetchall()

        conn.close()

    body = """
    <div class="panel">
    <h2>Search Books</h2>
    <form method="post">
      <label>Title, author, subject, genre or barcode
      <input name="term" required></label>
      <button type="submit">Search</button>
    </form>
    </div>
    """

    if request.method == "POST":
        body += "<h3>Search Results</h3>" + book_table(rows)

    return page("Search Book", body)


# =========================================================
# 6. PERSONALIZED BOOK RECOMMENDATIONS
# =========================================================

@app.route("/recommendations", methods=["GET", "POST"])
def recommendations():
    results = []
    reader_id = ""
    reader = None

    conn = connect_db()

    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        reader = conn.execute(
            "SELECT * FROM readers WHERE reader_id = ?", (reader_id,)
        ).fetchone()

        if not reader:
            flash("Reader ID was not found.", "error")
        else:
            interests = (reader["interests"] or "").lower()
            rated_books = conn.execute("""
                SELECT barcode, rating FROM ratings
                WHERE reader_id = ?
            """, (reader_id,)).fetchall()

            rated_ids = {row["barcode"] for row in rated_books}
            liked_ids = {row["barcode"] for row in rated_books if row["rating"] >= 4}

            books = conn.execute("""
                SELECT b.*, d.genre, d.description, d.reading_level
                FROM books b
                LEFT JOIN book_details d ON b.barcode = d.barcode
                ORDER BY b.title
            """).fetchall()

            scored = []
            for book in books:
                if book["barcode"] in rated_ids:
                    continue

                score = 0
                genre = (book["genre"] or "").lower()
                subject = (book["subject"] or "").lower()
                title = (book["title"] or "").lower()
                author = (book["author"] or "").lower()

                for word in re.findall(r"\w+", interests):
                    if len(word) > 2:
                        if word in genre:
                            score += 3
                        if word in subject:
                            score += 2
                        if word in title:
                            score += 2
                        if word in author:
                            score += 1

                for liked_id in liked_ids:
                    liked_book = get_book(conn, liked_id)
                    if liked_book:
                        if (liked_book["genre"] or "").lower() == genre and genre:
                            score += 2
                        if (liked_book["subject"] or "").lower() == subject and subject:
                            score += 1

                scored.append((score, book))

            scored.sort(key=lambda item: (-item[0], item[1]["title"] or ""))

            results = [item[1] for item in scored[:10]]

    readers = conn.execute(
        "SELECT reader_id, name FROM readers ORDER BY name"
    ).fetchall()
    conn.close()

    body = """
    <div class="panel">
    <h2>Personalized Book Recommendations</h2>
    <p>Recommendations use a reader's interests, subjects, genres and previous ratings.</p>
    <form method="post">
      <label>Select Reader
        <select name="reader_id" required>
          <option value="">Choose reader</option>
    """

    for item in readers:
        selected = "selected" if item["reader_id"] == reader_id else ""
        body += (
            f'<option value="{item["reader_id"]}" {selected}>'
            f'{item["reader_id"]} - {item["name"]}</option>'
        )

    body += """
        </select>
      </label>
      <button type="submit">Recommend Books</button>
    </form></div>
    """

    if request.method == "POST" and reader:
        body += "<div class='panel'><h3>Recommended Books</h3>"
        body += book_table(results)
        if not results:
            body += "<p>No unrated books were available for this reader.</p>"
        body += "</div>"

    return page("Book Recommendations", body)


# =========================================================
# 7. DASHBOARD
# =========================================================
# The dashboard is available at /.
# A web browser cannot stop the hosted server using an Exit button.


# =========================================================
# 8. BARCODE LOOKUP
# =========================================================

@app.route("/barcode", methods=["GET", "POST"])
def barcode_lookup():
    book = None

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()
        conn = connect_db()
        book = get_book(conn, barcode)
        conn.close()

        if not book:
            flash("No book was found with that barcode.", "error")

    body = """
    <div class="panel">
    <h2>Barcode Lookup</h2>
    <form method="post">
      <label>Scan or enter barcode<input name="barcode" required autofocus></label>
      <button type="submit">Find Book</button>
    </form>
    """

    if book:
        body += f"""
        <hr>
        <h3>Book Found</h3>
        <p><b>Barcode:</b> {book['barcode']}</p>
        <p><b>Title:</b> {book['title'] or ''}</p>
        <p><b>Author:</b> {book['author'] or ''}</p>
        <p><b>Subject:</b> {book['subject'] or ''}</p>
        <p><b>Genre:</b> {book['genre'] or ''}</p>
        <p><b>Description:</b> {book['description'] or ''}</p>
        """

    body += "</div>"
    return page("Barcode Lookup", body)


# =========================================================
# 9. REGISTER OR UPDATE READER
# =========================================================

@app.route("/readers", methods=["GET", "POST"])
def readers_page():
    conn = connect_db()

    if request.method == "POST":
        action = request.form.get("action", "register")
        reader_id = request.form.get("reader_id", "").strip()
        name = request.form.get("name", "").strip()
        interests = request.form.get("interests", "").strip()
        reading_level = request.form.get("reading_level", "").strip()

        if not name:
            conn.close()
            flash("Reader name is required.", "error")
            return redirect(url_for("readers_page"))

        if action == "update":
            if not reader_id or not reader_exists(conn, reader_id):
                conn.close()
                flash("Reader ID was not found.", "error")
                return redirect(url_for("readers_page"))

            conn.execute("""
                UPDATE readers
                SET name = ?, interests = ?, reading_level = ?
                WHERE reader_id = ?
            """, (name, interests, reading_level, reader_id))

            conn.commit()
            conn.close()
            flash("Reader details updated.")
            return redirect(url_for("readers_page"))

        if not reader_id:
            reader_id = generate_id(conn, "readers", "reader_id", "R")

        if reader_exists(conn, reader_id):
            conn.close()
            flash("Reader ID already exists. Choose another ID or use Update.", "error")
            return redirect(url_for("readers_page"))

        conn.execute("""
            INSERT INTO readers (reader_id, name, interests, reading_level)
            VALUES (?, ?, ?, ?)
        """, (reader_id, name, interests, reading_level))

        conn.commit()
        conn.close()
        flash(f"Reader registered successfully. Reader ID: {reader_id}")
        return redirect(url_for("readers_page"))

    readers = conn.execute(
        "SELECT * FROM readers ORDER BY name"
    ).fetchall()
    conn.close()

    body = """
    <div class="panel">
    <h2>Register Reader</h2>
    <form method="post">
      <input type="hidden" name="action" value="register">
      <label>Reader ID (leave blank to generate automatically)<input name="reader_id"></label>
      <label>Reader Name *<input name="name" required></label>
      <label>Reading Interests<input name="interests" placeholder="e.g. history, science, novels"></label>
      <label>Reading Level<input name="reading_level"></label>
      <button type="submit">Register Reader</button>
    </form>
    </div>

    <div class="panel" style="margin-top:16px">
    <h2>Update Reader</h2>
    <form method="post">
      <input type="hidden" name="action" value="update">
      <label>Existing Reader ID<input name="reader_id" required></label>
      <label>Reader Name *<input name="name" required></label>
      <label>Reading Interests<input name="interests"></label>
      <label>Reading Level<input name="reading_level"></label>
      <button type="submit">Update Reader</button>
    </form>
    </div>

    <div class="panel" style="margin-top:16px">
    <h2>Registered Readers</h2>
    """

    if readers:
        body += """
        <div class="table-wrap"><table>
        <tr><th>Reader ID</th><th>Name</th><th>Interests</th><th>Reading Level</th></tr>
        """
        for reader in readers:
            body += (
                f"<tr><td>{reader['reader_id']}</td>"
                f"<td>{reader['name'] or ''}</td>"
                f"<td>{reader['interests'] or ''}</td>"
                f"<td>{reader['reading_level'] or ''}</td></tr>"
            )
        body += "</table></div>"
    else:
        body += "<p>No readers registered yet.</p>"

    body += "</div>"
    return page("Readers", body)


# =========================================================
# 10. RATE BOOK
# =========================================================

@app.route("/ratings", methods=["GET", "POST"])
def ratings_page():
    conn = connect_db()

    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        barcode = request.form.get("barcode", "").strip()
        rating_text = request.form.get("rating", "").strip()

        try:
            rating = int(rating_text)
        except ValueError:
            rating = 0

        if not reader_exists(conn, reader_id):
            conn.close()
            flash("Reader ID was not found.", "error")
            return redirect(url_for("ratings_page"))

        if not book_exists(conn, barcode):
            conn.close()
            flash("Book barcode was not found.", "error")
            return redirect(url_for("ratings_page"))

        if rating < 1 or rating > 5:
            conn.close()
            flash("Rating must be between 1 and 5.", "error")
            return redirect(url_for("ratings_page"))

        conn.execute("""
            INSERT OR REPLACE INTO ratings (reader_id, barcode, rating)
            VALUES (?, ?, ?)
        """, (reader_id, barcode, rating))

        conn.commit()
        conn.close()
        flash("Book rating saved successfully.")
        return redirect(url_for("ratings_page"))

    readers = conn.execute(
        "SELECT reader_id, name FROM readers ORDER BY name"
    ).fetchall()

    books = conn.execute(
        "SELECT barcode, title FROM books ORDER BY title"
    ).fetchall()

    conn.close()

    body = """
    <div class="panel">
    <h2>Rate a Book</h2>
    <form method="post">
      <label>Reader
      <select name="reader_id" required>
        <option value="">Choose reader</option>
    """

    for reader in readers:
        body += (
            f'<option value="{reader["reader_id"]}">'
            f'{reader["reader_id"]} - {reader["name"]}</option>'
        )

    body += """
      </select></label>
      <label>Book
      <select name="barcode" required>
        <option value="">Choose book</option>
    """

    for book in books:
        body += (
            f'<option value="{book["barcode"]}">'
            f'{book["title"]} ({book["barcode"]})</option>'
        )

    body += """
      </select></label>
      <label>Rating
      <select name="rating" required>
        <option value="5">5 - Excellent</option>
        <option value="4">4 - Very good</option>
        <option value="3">3 - Good</option>
        <option value="2">2 - Fair</option>
        <option value="1">1 - Poor</option>
      </select></label>
      <button type="submit">Save Rating</button>
    </form>
    </div>
    """

    return page("Rate Book", body)


# =========================================================
# 11. BORROW BOOK
# =========================================================

@app.route("/borrow", methods=["GET", "POST"])
def borrow_book():
    conn = connect_db()

    if request.method == "POST":
        reader_id = request.form.get("reader_id", "").strip()
        barcode = request.form.get("barcode", "").strip()
        days_text = request.form.get("days", "14").strip()

        try:
            days = int(days_text)
        except ValueError:
            days = 14

        if days < 1 or days > 365:
            days = 14

        if not reader_exists(conn, reader_id):
            conn.close()
            flash("Reader ID was not found.", "error")
            return redirect(url_for("borrow_book"))

        if not book_exists(conn, barcode):
            conn.close()
            flash("Book barcode was not found.", "error")
            return redirect(url_for("borrow_book"))

        if book_is_on_loan(conn, barcode):
            conn.close()
            flash("This book is already on loan.", "error")
            return redirect(url_for("borrow_book"))

        borrowed = date.today()
        due = borrowed + timedelta(days=days)

        conn.execute("""
            INSERT INTO loans (reader_id, barcode, borrow_date, due_date, return_date)
            VALUES (?, ?, ?, ?, NULL)
        """, (
            reader_id,
            barcode,
            borrowed.isoformat(),
            due.isoformat()
        ))

        conn.commit()
        conn.close()
        flash(f"Book borrowed successfully. Due date: {due.isoformat()}")
        return redirect(url_for("loans_page"))

    readers = conn.execute(
        "SELECT reader_id, name FROM readers ORDER BY name"
    ).fetchall()

    books = conn.execute("""
        SELECT b.barcode, b.title FROM books b
        WHERE NOT EXISTS (
            SELECT 1 FROM loans l
            WHERE l.barcode = b.barcode AND l.return_date IS NULL
        )
        ORDER BY b.title
    """).fetchall()

    conn.close()

    body = """
    <div class="panel">
    <h2>Borrow a Book</h2>
    <form method="post">
      <label>Reader
      <select name="reader_id" required>
        <option value="">Choose reader</option>
    """

    for reader in readers:
        body += (
            f'<option value="{reader["reader_id"]}">'
            f'{reader["reader_id"]} - {reader["name"]}</option>'
        )

    body += """
      </select></label>
      <label>Available Book
      <select name="barcode" required>
        <option value="">Choose book</option>
    """

    for book in books:
        body += (
            f'<option value="{book["barcode"]}">'
            f'{book["title"]} ({book["barcode"]})</option>'
        )

    body += """
      </select></label>
      <label>Loan Period in Days<input type="number" name="days" value="14" min="1" max="365" required></label>
      <button type="submit">Record Borrowing</button>
    </form>
    </div>
    """

    return page("Borrow Book", body)


# =========================================================
# 12. RETURN BOOK
# =========================================================

@app.route("/return", methods=["GET", "POST"])
def return_book():
    conn = connect_db()

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()

        loan = conn.execute("""
            SELECT * FROM loans
            WHERE barcode = ? AND return_date IS NULL
            ORDER BY loan_id DESC LIMIT 1
        """, (barcode,)).fetchone()

        if not loan:
            conn.close()
            flash("No current loan was found for that barcode.", "error")
            return redirect(url_for("return_book"))

        conn.execute("""
            UPDATE loans SET return_date = ?
            WHERE loan_id = ?
        """, (date.today().isoformat(), loan["loan_id"]))

        conn.commit()
        conn.close()
        flash("Book return recorded successfully.")
        return redirect(url_for("loans_page"))

    current = conn.execute("""
        SELECT l.barcode, b.title, l.reader_id, r.name,
               l.borrow_date, l.due_date
        FROM loans l
        JOIN books b ON b.barcode = l.barcode
        JOIN readers r ON r.reader_id = l.reader_id
        WHERE l.return_date IS NULL
        ORDER BY l.due_date
    """).fetchall()

    conn.close()

    body = """
    <div class="panel">
    <h2>Return a Book</h2>
    <form method="post">
      <label>Book Barcode<input name="barcode" required></label>
      <button type="submit">Record Return</button>
    </form>
    </div>
    <div class="panel" style="margin-top:16px">
    <h3>Books Currently on Loan</h3>
    """

    if current:
        body += """
        <div class="table-wrap"><table>
        <tr><th>Barcode</th><th>Title</th><th>Reader</th><th>Borrowed</th><th>Due</th></tr>
        """
        for row in current:
            body += (
                f"<tr><td>{row['barcode']}</td>"
                f"<td>{row['title'] or ''}</td>"
                f"<td>{row['reader_id']} - {row['name'] or ''}</td>"
                f"<td>{row['borrow_date']}</td>"
                f"<td>{row['due_date']}</td></tr>"
            )
        body += "</table></div>"
    else:
        body += "<p>No books are currently on loan.</p>"

    body += "</div>"
    return page("Return Book", body)


# =========================================================
# 13. CURRENT LOANS
# =========================================================

@app.route("/loans")
def loans_page():
    conn = connect_db()

    loans = conn.execute("""
        SELECT l.loan_id, l.reader_id, r.name AS reader_name,
               l.barcode, b.title, l.borrow_date, l.due_date
        FROM loans l
        LEFT JOIN readers r ON r.reader_id = l.reader_id
        LEFT JOIN books b ON b.barcode = l.barcode
        WHERE l.return_date IS NULL
        ORDER BY l.due_date
    """).fetchall()

    conn.close()

    body = "<div class='panel'><h2>Current Loans</h2>"

    if loans:
        body += """
        <div class="table-wrap"><table>
        <tr><th>Loan ID</th><th>Reader</th><th>Barcode</th>
        <th>Book</th><th>Borrow Date</th><th>Due Date</th></tr>
        """
        for loan in loans:
            body += (
                f"<tr><td>{loan['loan_id']}</td>"
                f"<td>{loan['reader_id']} - {loan['reader_name'] or ''}</td>"
                f"<td>{loan['barcode']}</td>"
                f"<td>{loan['title'] or ''}</td>"
                f"<td>{loan['borrow_date']}</td>"
                f"<td>{loan['due_date']}</td></tr>"
            )
        body += "</table></div>"
    else:
        body += "<p>There are no current loans.</p>"

    body += "</div>"
    return page("Current Loans", body)


# =========================================================
# 14. OVERDUE BOOKS
# =========================================================

@app.route("/overdue")
def overdue_books():
    conn = connect_db()

    loans = conn.execute("""
        SELECT l.loan_id, l.reader_id, r.name AS reader_name,
               l.barcode, b.title, l.borrow_date, l.due_date
        FROM loans l
        LEFT JOIN readers r ON r.reader_id = l.reader_id
        LEFT JOIN books b ON b.barcode = l.barcode
        WHERE l.return_date IS NULL AND l.due_date < ?
        ORDER BY l.due_date
    """, (date.today().isoformat(),)).fetchall()

    conn.close()

    body = "<div class='panel'><h2>Overdue Books</h2>"

    if loans:
        body += """
        <div class="table-wrap"><table>
        <tr><th>Loan ID</th><th>Reader</th><th>Barcode</th>
        <th>Book</th><th>Borrow Date</th><th>Due Date</th></tr>
        """
        for loan in loans:
            body += (
                f"<tr><td>{loan['loan_id']}</td>"
                f"<td>{loan['reader_id']} - {loan['reader_name'] or ''}</td>"
                f"<td>{loan['barcode']}</td>"
                f"<td>{loan['title'] or ''}</td>"
                f"<td>{loan['borrow_date']}</td>"
                f"<td>{loan['due_date']}</td></tr>"
            )
        body += "</table></div>"
    else:
        body += "<p>There are no overdue books.</p>"

    body += "</div>"
    return page("Overdue Books", body)


# =========================================================
# ERROR HANDLING AND STARTUP
# =========================================================

@app.errorhandler(404)
def not_found(error):
    return page(
        "Page Not Found",
        "<div class='panel'><h2>Page not found</h2>"
        "<p>The requested page does not exist.</p>"
        "<a class='button' href='/'>Return to Dashboard</a></div>"
    ), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("An internal server error occurred.")
    return page(
        "System Error",
        "<div class='panel'><h2>Something went wrong</h2>"
        "<p>Please check the application logs for the error details.</p>"
        "<a class='button' href='/'>Return to Dashboard</a></div>"
    ), 500


# Initialize the tables when the app is imported by Gunicorn on Render.
setup_database()


if __name__ == "__main__":
    print("Smart Library Dashboard is starting.")
    print("Database:", DB_NAME)
    app.run(host="0.0.0.0", port=5000, debug=False)
