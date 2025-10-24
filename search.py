from config import DB_CONFIG

for key, value in DB_CONFIG.items():
    print(f"Проверяем {key} = {value}")
    for i, b in enumerate(value.encode('utf-8')):
        if b > 127:
            print(f"⚠️ Не-ASCII байт {b:#x} в позиции {i} строки {key}")
