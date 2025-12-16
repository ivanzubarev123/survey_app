import os
import sys
from flask import Flask, render_template, request, redirect, url_for, abort
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DB_URL = os.environ.get("DATABASE_URL")


def get_conn():
    if not DB_URL:
        print("DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    conn_str = DB_URL
    if "sslmode" not in DB_URL:
        conn_str += "?sslmode=require"

    return psycopg2.connect(conn_str, cursor_factory=RealDictCursor)


def fetch_data(query, params=None):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except:
        return None


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

        except:
            return "<h1>Ошибка создания сессии.</h1>", 500

    return render_template("start.html", id_opros=id_opros)


@app.route("/")
def index():
    surveys = fetch_data(
        "SELECT id_opros, nazvanie, opisanie FROM opros WHERE dostup = TRUE;"
    )

    if surveys is None:
        return "<h1>Ошибка подключения к базе данных.</h1>", 500

    return render_template("index.html", surveys=surveys)


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

        except:
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


index:
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Список опросов</title>
</head>
<body>
  <h1>Доступные опросы</h1>
  <ul>
    {% for survey in surveys %}
      <li>
        <a href="{{ url_for('start', id_opros=survey.id_opros) }}">
          {{ survey['nazvanie'] }}
        </a><br>
        <small>{{ survey['opisanie'] }}</small>
      </li>
    {% endfor %}
  </ul>
</body>
</html>


opros:
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{{ survey['nazvanie'] }}</title>
</head>
<body>

  <h1>{{ survey['nazvanie'] }}</h1>
  <p>{{ survey['opisanie'] }}</p>

  <form method="post" action="{{ url_for('opros', id_opros=id_opros, id_sessii=id_sessii) }}">
    {% for q in questions %}
      <p><strong>{{ q['tekst_vopros'] }}</strong></p>

      {% for v in q['variants'] %}
        {% if q['tip_voprosa'] == 'single' %}
          <label>
            <input type="radio" name="{{ q.id_vopros }}" value="{{ v.id_variant }}" required>
            {{ v['tekst_otveta'] }}
          </label><br>
        {% else %}
          <label>
            <input type="checkbox" name="{{ q.id_vopros }}" value="{{ v.id_variant }}">
            {{ v['tekst_otveta'] }}
          </label><br>
        {% endif %}
      {% endfor %}

      <hr>
    {% endfor %}

    <button type="submit">Отправить ответы</button>
  </form>

</body>
</html>


start:
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Начало опроса</title>
</head>
<body>
  <h1>Перед началом</h1>

  <form method="post" action="{{ url_for('start', id_opros=id_opros) }}">
    <p>
      <label>Пол:<br>
        <select name="pol" required>
          <option value="">Выберите...</option>
          <option value="М">Мужской</option>
          <option value="Ж">Женский</option>
        </select>
      </label>
    </p>

    <p>
      <label>Возраст:<br>
        <input type="number" name="vozrast" min="1" max="120" required>
      </label>
    </p>

    <button type="submit">Начать опрос</button>
  </form>
</body>
</html>


thanks:
<h2>Спасибо за участие!</h2>
<a href="/">Вернуться к списку опросов</a>
