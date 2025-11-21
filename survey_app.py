import os
import sys
from flask import Flask, render_template, request, redirect, url_for, abort
import psycopg2
from psycopg2.extras import RealDictCursor

# Инициализация Flask приложения
app = Flask(__name__)

# Получаем URL базы из переменных окружения Render
DB_URL = os.environ.get("DATABASE_URL")


# --- УТИЛИТЫ БАЗЫ ДАННЫХ ---

def get_conn():
    """Создает соединение с базой данных, используя RealDictCursor."""
    if not DB_URL:
        print("FATAL: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    conn_str = DB_URL
    if "sslmode" not in DB_URL:
        conn_str += "?sslmode=require"

    return psycopg2.connect(conn_str, cursor_factory=RealDictCursor)


def fetch_data(query, params=None):
    """Обобщенная функция для получения данных."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except psycopg2.Error as e:
        print(f"DATABASE ERROR during fetch: {e}", file=sys.stderr)
        return None


# --- СТАРТ ОПРОСА (выбор пола и возраста) ---

@app.route("/start/<int:id_opros>", methods=["GET", "POST"])
def start(id_opros):
    if request.method == "POST":
        pol = request.form.get("pol")
        vozrast = request.form.get("vozrast")

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO sessiya (id_opros, pol, vozrast)
                        VALUES (%s, %s, %s)
                        RETURNING id_sessii;
                        """,
                        (id_opros, pol, int(vozrast)),
                    )
                    id_sessii = cur.fetchone()["id_sessii"]
                    conn.commit()

            return redirect(url_for("opros", id_opros=id_opros, id_sessii=id_sessii))

        except Exception as e:
            print("ERROR CREATING SESSION:", e)
            return "<h1>Ошибка создания сессии.</h1>", 500

    return render_template("start.html", id_opros=id_opros)


# --- ГЛАВНАЯ ---

@app.route("/")
def index():
    surveys = fetch_data("SELECT id_opros, nazvanie, opisanie FROM opros WHERE dostup = TRUE;")

    if surveys is None:
        return "<h1>Ошибка подключения к базе данных.</h1>", 500

    return render_template("index.html", surveys=surveys)


# --- ОПРОС ---

@app.route("/opros/<int:id_opros>/<int:id_sessii>", methods=["GET", "POST"])
def opros(id_opros, id_sessii):

    # --- POST (сохраняем ответы) ---
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
                            if variant_id_str:
                                cur.execute(
                                    """
                                    INSERT INTO otvet_polzovatelya (id_sessii, id_vopros, id_variant)
                                    VALUES (%s, %s, %s);
                                    """,
                                    (id_sessii, question_id, int(variant_id_str)),
                                )

                conn.commit()

            return redirect(url_for("thanks"))

        except Exception as e:
            print(f"CRITICAL DATABASE ERROR during submission: {e}", file=sys.stderr)
            return "<h1>Ошибка: Не удалось сохранить ответы.</h1>", 500

    # --- GET (показываем опрос) ---

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


# --- СТРАНИЦА СПАСИБО ---

@app.route("/thanks")
def thanks():
    return render_template("thanks.html")


# --- ЗАПУСК СЕРВЕРА (локально) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
