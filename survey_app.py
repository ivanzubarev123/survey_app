import os
import sys
from flask import Flask, render_template, request, redirect, url_for, abort
from markupsafe import Markup
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
DB_URL = os.environ.get("DATABASE_URL")


import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

def get_conn():
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            sslmode="require",  # важно для Render
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("Ошибка подключения к базе:", e)
        raise


def fetch_data(query, params=None):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        print(e, file=sys.stderr)
        return None


def sanitize_string(s):
    if s:
        return Markup.escape(s.strip())
    return None


@app.route("/")
def index():
    nazvanie_filter = sanitize_string(request.args.get("nazvanie"))
    dostup_filter = request.args.get("dostup")
    
    query = "SELECT id_opros, nazvanie, opisanie FROM opros WHERE 1=1"
    params = []

    if nazvanie_filter:
        query += " AND nazvanie ILIKE %s"
        params.append(f"%{nazvanie_filter}%")
    if dostup_filter in ("true", "false"):
        query += " AND dostup = %s"
        params.append(dostup_filter == "true")

    surveys = fetch_data(query, params)
    if surveys is None:
        return "<h1>Ошибка подключения к базе данных.</h1>", 500

    return render_template("index.html", surveys=surveys)


@app.route('/start/<int:id_opros>', methods=['GET', 'POST'])
def start(id_opros):
    print("id_opros:", id_opros)  # должно печатать 4

    if request.method == 'POST':
        pol = request.form['pol']
        vozrast = request.form['vozrast']

        cur.execute("""
            INSERT INTO sessiya (id_opros, data_sessii, pol, vozrast)
            VALUES (%s, NOW(), %s, %s)
            RETURNING id_sessii;
        """, (id_opros, pol, vozrast))

        id_sessii = cur.fetchone()[0]
        conn.commit()

        return redirect(url_for('vopros', id_sessii=id_sessii))
    return render_template('start.html', id_opros=id_opros)


@app.route("/opros/<int:id_opros>/<int:id_sessii>", methods=["GET", "POST"])
def opros(id_opros, id_sessii):
    if request.method == "POST":
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    for question_id_str in request.form:
                        if not question_id_str.isdigit():
                            continue

                        question_id = int(question_id_str)
                        variant_ids = request.form.getlist(question_id_str)
                        for variant_id_str in variant_ids:
                            if not variant_id_str.isdigit():
                                continue
                            cur.execute(
                                """
                                INSERT INTO otvet_polzovatelya (id_sessii, id_vopros, id_variant)
                                VALUES (%s, %s, %s);
                                """,
                                (id_sessii, question_id, int(variant_id_str)),
                            )
                    cur.execute(
                        "UPDATE sessiya SET vremya_konca = NOW() WHERE id_sessii = %s;",
                        (id_sessii,),
                    )
                conn.commit()
            return redirect(url_for("thanks"))
        except Exception as e:
            print(e, file=sys.stderr)
            return "<h1>Ошибка: Не удалось сохранить ответы.</h1>", 500

    survey_data = fetch_data(
        "SELECT nazvanie, opisanie FROM opros WHERE id_opros = %s AND dostup = TRUE;",
        (id_opros,),
    )
    if not survey_data:
        abort(404)

    questions_data = fetch_data(
        """
        SELECT id_vopros, tekst_vopros, tip_voprosa
        FROM vopros
        WHERE id_opros = %s
        ORDER BY poryadok;
        """,
        (id_opros,),
    )

    questions = []
    for q in questions_data:
        variants = fetch_data(
            "SELECT id_variant, tekst_otveta FROM variant_otveta WHERE id_vopros = %s;",
            (q["id_vopros"],),
        )
        q["variants"] = variants or []
        questions.append(q)

    return render_template(
        "opros.html",
        id_opros=id_opros,
        id_sessii=id_sessii,
        survey=survey_data[0],
        questions=questions,
    )


@app.route("/thanks")
def thanks():
    return render_template("thanks.html")


@app.route("/stats/<int:id_opros>")
def stats(id_opros):
    stats_data = fetch_data(
        """
        SELECT pol,
               CASE
                   WHEN vozrast < 18 THEN '<18'
                   WHEN vozrast BETWEEN 18 AND 25 THEN '18-25'
                   WHEN vozrast BETWEEN 26 AND 35 THEN '26-35'
                   WHEN vozrast BETWEEN 36 AND 50 THEN '36-50'
                   ELSE '50+'
               END AS vozrast_gruppa,
               COUNT(*) as count
        FROM sessiya
        WHERE id_opros = %s
        GROUP BY pol, vozrast_gruppa
        ORDER BY pol, vozrast_gruppa;
        """,
        (id_opros,),
    )

    return render_template("stats.html", stats=stats_data, id_opros=id_opros)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
