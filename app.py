from flask import Flask, render_template, request, redirect, session, flash, make_response
import sqlite3, os, io
from datetime import datetime
from functools import wraps
from config import Config

from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors

app = Flask(__name__)
app.config.from_object(Config)

# ================= DB =================
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ================= AUTH =================
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return wrap

# ================= LOGIN =================
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (u,p)).fetchone()

        if user:
            session['user'] = u
            return redirect('/dashboard')
        else:
            flash("Login gagal")

    return render_template('login.html')

# ================= DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()

    audit = db.execute("""
        SELECT status, COUNT(*) jumlah 
        FROM audit 
        GROUP BY status
    """).fetchall()

    today = datetime.today().date()
    perawat = db.execute("SELECT * FROM perawat").fetchall()

    notif = []

    for p in perawat:
        for field in ['masa_sip', 'masa_spk']:
            tgl_str = p[field]

            if tgl_str:
                try:
                    tgl = datetime.strptime(tgl_str, "%Y-%m-%d").date()
                    selisih = (tgl - today).days

                    if selisih < 0:
                        notif.append(f"{p['nama']} - {field.upper()} SUDAH EXPIRE")
                    elif selisih <= 30:
                        notif.append(f"{p['nama']} - {field.upper()} akan expire ({selisih} hari lagi)")
                except:
                    pass

    profesi = db.execute("""
        SELECT 
            CASE 
                WHEN LOWER(TRIM(profesi)) = 'bidan' THEN 'Bidan'
                ELSE 'Perawat'
            END as profesi,
            COUNT(*) jumlah
        FROM perawat
        GROUP BY 
            CASE 
                WHEN LOWER(TRIM(profesi)) = 'bidan' THEN 'Bidan'
                ELSE 'Perawat'
            END
    """).fetchall()

    jenjang = db.execute("""
        SELECT jenjang, COUNT(*) jumlah 
        FROM perawat 
        GROUP BY jenjang
    """).fetchall()

    return render_template('dashboard.html',
        audit=audit,
        notif=notif,
        profesi=profesi,
        jenjang=jenjang
    )

# ================= PERAWAT =================
@app.route('/perawat', methods=['GET','POST'])
@login_required
def perawat():
    db = get_db()

    if request.method == 'POST':
        db.execute('''
        INSERT INTO perawat 
        (nama,tgl_lahir,jenjang,kampus,pendidikan,no_str,masa_str,no_sip,masa_sip,no_spk,masa_spk,profesi)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            request.form['nama'],
            request.form['tgl_lahir'],
            request.form['jenjang'],
            request.form['kampus'],
            request.form['pendidikan'],
            request.form['no_str'],
            request.form['masa_str'],
            request.form['no_sip'],
            request.form['masa_sip'],
            request.form['no_spk'],
            request.form['masa_spk'],
            request.form['profesi'],
        ))
        db.commit()

    data = db.execute("SELECT * FROM perawat").fetchall()
    return render_template('perawat.html', data=data)

@app.route('/perawat/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_perawat(id):
    db = get_db()
    data = db.execute("SELECT * FROM perawat WHERE id=?", (id,)).fetchone()

    if request.method == 'POST':
        db.execute('''
        UPDATE perawat SET 
        nama=?, tgl_lahir=?, jenjang=?, kampus=?, pendidikan=?,
        no_str=?, masa_str=?, no_sip=?, masa_sip=?, no_spk=?, masa_spk=?, profesi=?
        WHERE id=?
        ''', (
            request.form['nama'],
            request.form['tgl_lahir'],
            request.form['jenjang'],
            request.form['kampus'],
            request.form['pendidikan'],
            request.form['no_str'],
            request.form['masa_str'],
            request.form['no_sip'],
            request.form['masa_sip'],
            request.form['no_spk'],
            request.form['masa_spk'],
            request.form['profesi'],
            id
        ))
        db.commit()
        return redirect('/perawat')

    return render_template('perawat_edit.html', data=data)

@app.route('/perawat/delete/<int:id>')
@login_required
def delete_perawat(id):
    db = get_db()
    db.execute("DELETE FROM perawat WHERE id=?", (id,))
    db.commit()
    return redirect('/perawat')

# ================= AUDIT =================
@app.route('/audit', methods=['GET','POST'])
@login_required
def audit():
    db = get_db()

    if request.method == 'POST':
        tanggal = request.form.get('tanggal')
        unit = request.form.get('unit')
        temuan = request.form.get('temuan')
        rekomendasi = request.form.get('rekomendasi')
        status = request.form.get('status')

        file_before = request.files.get('foto_before')
        file_after = request.files.get('foto_after')

        filename_before = ""
        filename_after = ""

    # ================= BEFORE =================
        if file_before and file_before.filename:
            filename_before = file_before.filename
            file_before.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_before))

    # ================= AFTER =================
        if file_after and file_after.filename:
            filename_after = file_after.filename
            file_after.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_after))

    # ================= SIMPAN DB =================
        db.execute('''
        INSERT INTO audit (tanggal, unit, foto, foto_after, temuan, rekomendasi, status)
        VALUES (?,?,?,?,?,?,?)
        ''', (tanggal, unit, filename_before, filename_after, temuan, rekomendasi, status))

        db.commit()

    data = db.execute("SELECT * FROM audit").fetchall()
    return render_template('audit.html', data=data)

# ================= EDIT AUDIT =================
@app.route('/audit/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_audit(id):
    db = get_db()
    data = db.execute("SELECT * FROM audit WHERE id=?", (id,)).fetchone()

    if request.method == 'POST':
        tanggal = request.form.get('tanggal')
        unit = request.form.get('unit')
        temuan = request.form.get('temuan')
        rekomendasi = request.form.get('rekomendasi')
        status = request.form.get('status')

        file = request.files.get('foto')

        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = data['foto']

        db.execute('''
        UPDATE audit 
        SET tanggal=?, unit=?, foto=?, temuan=?, rekomendasi=?, status=?
        WHERE id=?
        ''', (tanggal, unit, filename, temuan, rekomendasi, status, id))

        db.commit()
        return redirect('/audit')

    return render_template('audit_edit.html', data=data)

# ================= DELETE =================
@app.route('/audit/delete/<int:id>')
@login_required
def delete_audit(id):
    db = get_db()
    db.execute("DELETE FROM audit WHERE id=?", (id,))
    db.commit()
    return redirect('/audit')

# ================= HEADER PDF =================
def header(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize

    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        canvas.drawImage(logo_path, width/2 - 85, height - 80, width=170, height=55)

    canvas.setFillColorRGB(0, 0.45, 0.75)
    canvas.setFont("Helvetica", 8)

    canvas.drawCentredString(width/2, height - 95,
        "Jl. HOS. Cokroaminoto No 4A, Tangerang")

    canvas.drawCentredString(width/2, height - 105,
        "Telp : 0217371919 | www.rsmurniteguh.com")

    canvas.setStrokeColorRGB(0, 0.45, 0.75)
    canvas.setLineWidth(2)
    canvas.line(40, height - 115, width - 40, height - 115)

    canvas.restoreState()

@app.route('/audit/pdf')
@login_required
def export_pdf():
    db = get_db()
    data = db.execute("SELECT * FROM audit").fetchall()

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=140,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    styles['Title'].alignment = TA_CENTER

    elements = []

    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>LAPORAN AUDIT KEPERAWATAN</b>", styles['Title']))
    elements.append(Spacer(1, 15))

    for i, d in enumerate(data, start=1):
        elements.append(Paragraph(f"<b>{i}. Temuan:</b> {d['temuan']}", styles['Normal']))
        elements.append(Paragraph(f"<b>Rekomendasi:</b> {d['rekomendasi']}", styles['Normal']))
        elements.append(Paragraph(f"<b>Status:</b> {d['status']}", styles['Normal']))

        if d['foto']:
            img_path = os.path.join("static/uploads", d['foto'])
            if os.path.exists(img_path):
                img = Image(img_path)
                max_width = 250
                img.drawWidth = max_width
                img.drawHeight = img.imageHeight * (max_width / img.imageWidth)
                elements.append(Spacer(1, 10))
                elements.append(img)

        elements.append(Spacer(1, 20))

    doc.build(elements, onFirstPage=header, onLaterPages=header)

    buffer.seek(0)

    return make_response(buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'inline; filename="laporan_audit.pdf"'
    })



# ================= PDF 2 =================
@app.route('/audit/pdf2')
@login_required
def export_pdf_tabel():
    db = get_db()
    data = db.execute("SELECT * FROM audit").fetchall()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10,
        leftMargin=10,
        topMargin=10,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # ================= JUDUL =================
    elements.append(Paragraph("<b>Laporan Temuan Ronde Keperawatan</b>", styles['Title']))
    elements.append(Spacer(1, 5))

    # ================= LOOP =================
    for d in data:

        img_before = ""
        img_after = ""

        # ================= FOTO BEFORE =================
        if d['foto']:
            path = os.path.join("static/uploads", d['foto'])
            if os.path.exists(path):
                img = Image(path)
                max_width = 160
                ratio = max_width / img.imageWidth
                img.drawWidth = max_width
                img.drawHeight = img.imageHeight * ratio
                img_before = img

        # ================= FOTO AFTER =================
        if d['foto_after']:
            path2 = os.path.join("static/uploads", d['foto_after'])
            if os.path.exists(path2):
                img2 = Image(path2)
                max_width = 140
                ratio = max_width / img2.imageWidth
                img2.drawWidth = max_width
                img2.drawHeight = img2.imageHeight * ratio
                img_after = img2

        # ================= TABEL FOTO =================
        foto_table = Table([
            [
                Paragraph("<b>Before (Temuan)</b>", styles['Normal']),
                Paragraph("<b>After (Perbaikan)</b>", styles['Normal'])
            ],
            [img_before, img_after]
        ], colWidths=[190, 190])

        foto_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

        # ================= TABEL UTAMA =================
        table = Table([
            ["Tanggal", d['tanggal']],
            ["Unit", d['unit']],
            ["Temuan", Paragraph(d['temuan'], styles['Normal'])],
            ["Rekomendasi", Paragraph(d['rekomendasi'], styles['Normal'])],
            ["Status", d['status']],
            ["Dokumentasi", foto_table]
        ], colWidths=[110, 410])

        table.setStyle(TableStyle([
            # 🔥 GARIS FULL SEPERTI FORM
            ('GRID', (0,0), (-1,-1), 1, colors.black),

            # HEADER KIRI ABU
            ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),

            # ALIGNMENT
            ('VALIGN', (0,0), (-1,-1), 'TOP'),

            # PADDING BIAR RAPI
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

    doc.build(elements)

    buffer.seek(0)

    return make_response(buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'inline; filename="laporan_audit_tabel.pdf"'
    })
# ================= RUN =================
if __name__ == "__main__":
    app.run()
class Config:
    SECRET_KEY = "supersecretkey"
    UPLOAD_FOLDER = "static/uploads"
Flask
gunicorn
reportlab
