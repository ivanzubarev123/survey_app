from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from config import DB_CONFIG
import os

app = Flask(__name__)

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

@app.route('/')
def index():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id_opros, nazvanie, opisanie FROM opros ORDER BY data DESC;")
        opros_list = cur.fetchall()
    return render_template('index.html', opros_list=opros_list)

@app.route('/opros/<int:id_opros>')
def show_opros(id_opros):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT tekst_vopros, id_vopros, tip_voprosa FROM vopros WHERE id_opros = %s ORDER BY poryadok;", (id_opros,))
        voprosy = cur.fetchall()
        voprosy_polnye = []
        for tekst_vopros, id_vopros, tip in voprosy:
            cur.execute("SELECT id_variant, tekst_otveta FROM variant_otveta WHERE id_vopros = %s;", (id_vopros,))
            variants = cur.fetchall()
            voprosy_polnye.append((id_vopros, tekst_vopros, tip, variants))
    return render_template('opros.html', id_opros=id_opros, voprosy=voprosy_polnye)

@app.route('/submit/<int:id_opros>', methods=['POST'])
def submit(id_opros):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO sessiya (id_opros) VALUES (%s) RETURNING id_sessii;", (id_opros,))
        id_sessii = cur.fetchone()[0]

        for key, value in request.form.items():
            if key.startswith('q_'):
                id_vopros = int(key.split('_')[1])
                cur.execute(
                    "INSERT INTO otvet_polzovatelya (id_sessii, id_vopros, id_variant) VALUES (%s, %s, %s)",
                    (id_sessii, id_vopros, value)
                )
    return redirect(url_for('thanks'))

@app.route('/thanks')
def thanks():
    return render_template('thanks.html')

if __name__ == '__main__':
    app.run(debug=True)
