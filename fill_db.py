import psycopg2
from faker import Faker
import random
from config import DB_CONFIG

fake = Faker('ru_RU')

def fill_db(n_opros=10, n_vopros_per_opros=10, n_variant_per_vopros=10):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for _ in range(n_opros):
        cur.execute(
            "INSERT INTO opros (nazvanie, opisanie, data) VALUES (%s, %s, CURRENT_DATE) RETURNING id_opros;",
            (fake.sentence(nb_words=3), fake.text())
        )
        id_opros = cur.fetchone()[0]

        for i in range(1, n_vopros_per_opros + 1):
            tip = random.choice(['single', 'multiple'])
            cur.execute(
                "INSERT INTO vopros (id_opros, tekst_vopros, poryadok, tip_voprosa) VALUES (%s, %s, %s, %s) RETURNING id_vopros;",
                (id_opros, fake.sentence(nb_words=6), i, tip)
            )
            id_vopros = cur.fetchone()[0]

            for _ in range(n_variant_per_vopros):
                cur.execute(
                    "INSERT INTO variant_otveta (id_vopros, tekst_otveta) VALUES (%s, %s);",
                    (id_vopros, fake.word())
                )

    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    fill_db()
    print("База успешно заполнена тестовыми данными!")
