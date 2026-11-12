from connection import get_connection


def main():
    print("Подключаюсь к Postgres...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Проверка 1: SELECT 1 — что база вообще отвечает
            cur.execute("SELECT 1")
            print(f"SELECT 1 → {cur.fetchone()}")

            # Проверка 2: сколько строк в prices
            cur.execute("SELECT count(*) FROM prices")
            count = cur.fetchone()[0]
            print(f"SELECT count(*) FROM prices → {count}")

            # Проверка 3: список схем (должны быть public и, возможно, core)
            cur.execute("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
            schemas = [row[0] for row in cur.fetchall()]
            print(f"Схемы в базе: {schemas}")

    print("✅ Подключение работает.")


if __name__ == "__main__":
    main()