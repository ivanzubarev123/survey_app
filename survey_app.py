# survey_app.py
import os
from flask import Flask, render_template, request, redirect
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Получаем URL базы из переменных окружения Render
DB_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

@app.route("/")
def index():
    # Список доступных опросов
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM opros WHERE dostup = TRUE;")
            surveys = cur.fetchall()
    return render_template("index.html", surveys=surveys)

@app.route("/opros/<int:id_opros>", methods=["GET", "POST"])
def opros(id_opros):
    if request.method == "POST":
        answers = request.form  # словарь с ответами
        with get_conn() as conn:
            with conn.cursor() as cur:
                # создаём сессию пользователя
                cur.execute("INSERT INTO sessiya (id_opros) VALUES (%s) RETURNING id_sessii;", (id_opros,))
                id_sessii = cur.fetchone()["id_sessii"]
                # сохраняем ответы
                for key, value in answers.items():
                    cur.execute(
                        "INSERT INTO otvet_polzovatelya (id_sessii, id_vopros, id_variant) VALUES (%s, %s, %s);",
                        (id_sessii, key, value)
                    )
                conn.commit()
        return redirect("/thanks")
    else:
        # Получаем вопросы и варианты ответов
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM vopros WHERE id_opros = %s ORDER BY poryadok;", (id_opros,))
                questions = cur.fetchall()
                for q in questions:
                    cur.execute("SELECT * FROM variant_otveta WHERE id_vopros = %s;", (q["id_vopros"],))
                    q["variants"] = cur.fetchall()
        return render_template("opros.html", questions=questions, id_opros=id_opros)

@app.route("/thanks")
def thanks():
    return render_template("thanks.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render назначает порт через переменную окружения
    app.run(host="0.0.0.0", port=port)
