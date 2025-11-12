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
        # Это должно быть обработано во время деплоя, но на всякий случай
        print("FATAL: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    
    # Render может потребовать 'sslmode=require' в продакшене
    conn_str = DB_URL
    if 'sslmode' not in DB_URL:
        conn_str += "?sslmode=require"
        
    return psycopg2.connect(conn_str, cursor_factory=RealDictCursor)

def fetch_data(query, params=None):
    """Обобщенная функция для получения данных с обработкой ошибок."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except psycopg2.Error as e:
        print(f"DATABASE ERROR during fetch: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"GENERAL ERROR during fetch: {e}", file=sys.stderr)
        return None

# --- РОУТЫ ПРИЛОЖЕНИЯ ---

@app.route("/")
def index():
    """Отображает список доступных опросов."""
    surveys = fetch_data("SELECT id_opros, nazvanie, opisanie FROM opros WHERE dostup = TRUE;")
    
    # Обработка случая, когда опросы не найдены или произошла ошибка БД
    if surveys is None:
         return "<h1>Ошибка подключения к базе данных. Проверьте логи Render.</h1>", 500
         
    return render_template("index.html", surveys=surveys)

@app.route("/opros/<int:id_opros>", methods=["GET", "POST"])
def opros(id_opros):
    # --- ОБРАБОТКА POST (Отправка ответов) ---
    if request.method == "POST":
        
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    # 1. Создание новой сессии
                    cur.execute("INSERT INTO sessiya (id_opros) VALUES (%s) RETURNING id_sessii;", (id_opros,))
                    id_sessii = cur.fetchone()["id_sessii"]
                    
                    # 2. Обработка всех ответов
                    # Итерируемся по ключам формы (ключ = ID вопроса)
                    for question_id_str in request.form:
                        # Игнорируем технические поля, если они есть
                        if not question_id_str.isdigit():
                            continue 
                            
                        question_id = int(question_id_str)

                        # Используем getlist(), чтобы получить ВСЕ выбранные значения (даже если одно)
                        variant_ids = request.form.getlist(question_id_str)
                        
                        # Сохраняем каждый выбранный вариант ответа
                        for variant_id_str in variant_ids:
                            # Проверяем, что значение не пустое
                            if variant_id_str:
                                cur.execute(
                                    "INSERT INTO otvet_polzovatelya (id_sessii, id_vopros, id_variant) VALUES (%s, %s, %s);",
                                    (id_sessii, question_id, int(variant_id_str))
                                )
                    
                    conn.commit()
            
            return redirect(url_for("thanks"))
            
        except psycopg2.Error as e:
            # Логирование критической ошибки
            print(f"CRITICAL DATABASE ERROR during submission: {e}", file=sys.stderr)
            return "<h1>Ошибка: Не удалось сохранить ответы. Проверьте логи.</h1>", 500


    # --- ОБРАБОТКА GET (Отображение опроса) ---
    
    # 1. Получаем общие данные опроса (название, описание)
    survey_data = fetch_data("SELECT nazvanie, opisanie FROM opros WHERE id_opros = %s AND dostup = TRUE;", (id_opros,))
    if not survey_data:
        abort(404) # Опрос не найден
    
    # 2. Получаем вопросы для этого опроса
    questions_data = fetch_data(
        "SELECT id_vopros, tekst, tip FROM vopros WHERE id_opros = %s ORDER BY poryadok;", 
        (id_opros,)
    )

    questions = []
    
    # 3. Для каждого вопроса получаем его варианты ответа
    for q in questions_data:
        variants = fetch_data(
            "SELECT id_variant, tekst FROM variant_otveta WHERE id_vopros = %s ORDER BY poryadok;",
            (q["id_vopros"],)
        )
        # Добавляем варианты в словарь вопроса
        q["variants"] = variants or []
        questions.append(q)

    return render_template(
        "opros.html", 
        id_opros=id_opros, 
        survey=survey_data[0], 
        questions=questions
    )

@app.route("/thanks")
def thanks():
    """Страница благодарности."""
    return render_template("thanks.html")

# --- ЗАПУСК СЕРВЕРА (Dev-режим для локального тестирования, Gunicorn для Render) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # ВНИМАНИЕ: Это DEV-сервер. Для Render используйте gunicorn survey_app:app
    app.run(host="0.0.0.0", port=port, debug=True)
