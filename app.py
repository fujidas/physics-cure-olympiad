from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3, os, io
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "secret123"

# ---- Database Setup ----
DB = "data.db"

def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()

        # Admin table
        cur.execute('''CREATE TABLE IF NOT EXISTS admin(
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            exam_date TEXT,
            venue TEXT,
            logo TEXT)''')

        # Student table
        cur.execute('''CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            class_name TEXT,
            result REAL,
            mock REAL)''')

        # Default admin
        cur.execute("SELECT * FROM admin")
        if not cur.fetchone():
            cur.execute("INSERT INTO admin(username,password,exam_date,venue,logo) VALUES(?,?,?,?,?)",
                        ("admin", generate_password_hash("admin123"), "2025-12-01", "Online", "logo.png"))
        con.commit()

init_db()

# ---- HOME PAGE ----
@app.route('/')
def home():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT exam_date, venue, logo FROM admin WHERE id=1")
    exam_date, venue, logo = cur.fetchone()
    return render_template("index.html", exam_date=exam_date, venue=venue, logo=logo)

# ---- REGISTRATION ----
@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']
    class_name = request.form['class']

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("INSERT INTO students(name,email,phone,class_name,result,mock) VALUES(?,?,?,?,?,?)",
                    (name, email, phone, class_name, 0, 0))
        con.commit()

    cur = con.cursor()
    cur.execute("SELECT exam_date, venue, logo FROM admin WHERE id=1")
    exam_date, venue, logo = cur.fetchone()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    logo_path = os.path.join("static", logo)

    if os.path.exists(logo_path):
        img = ImageReader(logo_path)
        pdf.drawImage(img, width/2 - 50, height - 150, width=100, height=100, mask='auto')

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(width / 2, height - 180, "Talent Test Admit Card")

    pdf.setFont("Helvetica", 14)
    pdf.drawString(100, height - 230, f"Name: {name}")
    pdf.drawString(100, height - 260, f"Class: {class_name}")
    pdf.drawString(100, height - 290, f"Email: {email}")
    pdf.drawString(100, height - 320, f"Phone: {phone}")
    pdf.drawString(100, height - 360, f"Exam Date: {exam_date}")
    pdf.drawString(100, height - 390, f"Venue: {venue}")

    pdf.setFont("Helvetica-Oblique", 12)
    pdf.drawString(100, height - 430, "Please bring this Admit Card during the exam.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Admit_Card_{name}.pdf",
        mimetype='application/pdf'
    )

# ---- RESULT PAGE ----
@app.route('/result', methods=['GET', 'POST'])
def result():
    data = None
    if request.method == 'POST':
        email = request.form['email']
        with sqlite3.connect(DB) as con:
            cur = con.cursor()
            cur.execute("SELECT name, class_name, result, mock FROM students WHERE email=?", (email,))
            data = cur.fetchone()
    return render_template("result.html", data=data)

# ---- ADMIN LOGIN ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DB) as con:
            cur = con.cursor()
            cur.execute("SELECT password FROM admin WHERE username=?", (username,))
            user = cur.fetchone()

            if user and check_password_hash(user[0], password):
                session['admin'] = username
                return redirect('/admin')
    return render_template('login.html')

# ---- ADMIN DASHBOARD ----
@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect('/login')

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT * FROM students ORDER BY id DESC")
    students = cur.fetchall()

    cur.execute("SELECT exam_date, venue, logo FROM admin WHERE id=1")
    exam_date, venue, logo = cur.fetchone()

    # ✅ Determine the weekday (e.g., Monday, Tuesday)
    try:
        date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
        exam_day = date_obj.strftime("%A")
    except Exception:
        exam_day = ""

    return render_template("admin.html",
                           students=students,
                           exam_date=exam_date,
                           exam_day=exam_day,
                           venue=venue,
                           logo=logo)

# ---- UPDATE EXAM INFO ----
@app.route('/update_exam', methods=['POST'])
def update_exam():
    if 'admin' not in session:
        return redirect('/login')

    date = request.form['exam_date']
    venue = request.form['venue']

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("UPDATE admin SET exam_date=?, venue=? WHERE id=1", (date, venue))
        con.commit()
    return redirect('/admin')

# ---- UPDATE STUDENT ----
@app.route('/update_result/<int:id>', methods=['POST'])
def update_result(id):
    result = request.form['result']
    mock = request.form['mock']
    class_name = request.form['class']

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("UPDATE students SET result=?, mock=?, class_name=? WHERE id=?",
                    (result, mock, class_name, id))
        con.commit()
    return redirect('/admin')

# ---- DELETE STUDENT ----
@app.route('/delete_student/<int:id>')
def delete_student(id):
    if 'admin' not in session:
        return redirect('/login')

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM students WHERE id=?", (id,))
        con.commit()
    return redirect('/admin')

# ---- CHANGE PASSWORD ----
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'admin' not in session:
        return redirect('/login')

    current = request.form['current_password']
    new = request.form['new_password']
    confirm = request.form['confirm_password']

    if new != confirm:
        return "New passwords do not match!"

    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT password FROM admin WHERE id=1")
        old_pw = cur.fetchone()[0]

        if not check_password_hash(old_pw, current):
            return "Current password incorrect!"

        cur.execute("UPDATE admin SET password=? WHERE id=1", (generate_password_hash(new),))
        con.commit()
    return redirect('/admin')

# ---- DOWNLOAD EXCEL ----
@app.route('/download')
def download():
    if 'admin' not in session:
        return redirect('/login')

    con = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT name, email, phone, class_name, result, mock FROM students", con)
    file_path = "results.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ---- LOGOUT ----
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)