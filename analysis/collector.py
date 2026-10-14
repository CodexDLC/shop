"""Bounded Google autocomplete collection; Python standard library only."""
import argparse
import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://suggestqueries.google.com/complete/search"


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_response(raw):
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[0], str):
        raise ValueError("Unexpected autocomplete response")
    values = payload[1]
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("Unexpected suggestion list")
    # Preserve original ranks even when a response contains duplicate phrases.
    seen = set()
    result = []
    for rank, phrase in enumerate(values, 1):
        phrase = phrase.strip()
        if phrase and phrase not in seen:
            seen.add(phrase)
            result.append((rank, phrase))
    return result


def open_database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
            finished_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fetches (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
            query TEXT NOT NULL, fetched_at TEXT NOT NULL, status TEXT NOT NULL,
            http_status INTEGER, error TEXT
        );
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY, phrase TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS observations (
            fetch_id INTEGER NOT NULL REFERENCES fetches(id),
            suggestion_id INTEGER NOT NULL REFERENCES suggestions(id),
            rank INTEGER NOT NULL,
            PRIMARY KEY (fetch_id, suggestion_id)
        );
        CREATE INDEX IF NOT EXISTS fetch_query_status ON fetches(query, status);
    """)
    return connection


def record_fetch(connection, run_id, query, suggestions=(), status="success", http_status=200, error=None):
    with connection:
        fetch_id = connection.execute(
            "INSERT INTO fetches(run_id, query, fetched_at, status, http_status, error) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, query, now(), status, http_status, error),
        ).lastrowid
        for rank, phrase in suggestions:
            connection.execute("INSERT OR IGNORE INTO suggestions(phrase) VALUES (?)", (phrase,))
            suggestion_id = connection.execute("SELECT id FROM suggestions WHERE phrase = ?", (phrase,)).fetchone()[0]
            connection.execute("INSERT OR IGNORE INTO observations VALUES (?, ?, ?)", (fetch_id, suggestion_id, rank))
    return fetch_id


def export_csv(connection, path):
    rows = connection.execute("""
        SELECT s.phrase, f.query, o.rank, f.fetched_at, 'Google autocomplete', 'de', 'de'
        FROM observations o JOIN suggestions s ON s.id = o.suggestion_id
        JOIN fetches f ON f.id = o.fetch_id
        ORDER BY s.phrase, f.fetched_at, f.query
    """)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["query", "source_query", "rank", "observed_at_utc", "source", "requested_language", "requested_country"])
        for row in rows:
            # Prevent Excel from interpreting an external phrase as a formula.
            writer.writerow(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in row])


def make_queries(seeds, expand):
    seen = set()
    for seed in seeds:
        seed = seed.strip()
        if not seed or seed.startswith("#"):
            continue
        queries = [seed]
        if expand:
            queries.extend(seed + " " + suffix for suffix in ("sale", "outlet", "herren", "string", *"abcdefghijklmnopqrstuvwxyz"))
        for query in queries:
            if query not in seen:
                seen.add(query)
                yield query


def fetch(query, timeout):
    url = ENDPOINT + "?" + urlencode({"client": "firefox", "hl": "de", "gl": "de", "q": query})
    request = Request(url, headers={"User-Agent": "KeywordResearch/0.1", "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP status: " + str(response.status))
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Response exceeds size limit")
        return parse_response(raw.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, default=Path(__file__).with_name("seeds.txt"))
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--expand", action="store_true", help="Add suffixes to each seed")
    parser.add_argument("--refresh", action="store_true", help="Fetch previously successful queries again")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    if args.max_requests < 1 or args.delay < 1 or args.timeout <= 0:
        parser.error("max-requests must be positive, delay >= 1 second, timeout > 0")
    seeds = [] if args.export_only else args.seeds.read_text(encoding="utf-8-sig").splitlines()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    database = args.data_dir / "queries.sqlite3"
    csv_path = args.data_dir / "suggestions.csv"
    connection = open_database(database)
    stopped = False
    attempted = 0
    try:
        if not args.export_only:
            with connection:
                run_id = connection.execute("INSERT INTO runs(started_at, status) VALUES (?, 'running')", (now(),)).lastrowid
            try:
                for query in make_queries(seeds, args.expand):
                    if attempted >= args.max_requests:
                        break
                    if not args.refresh and connection.execute("SELECT 1 FROM fetches WHERE query = ? AND status = 'success' LIMIT 1", (query,)).fetchone():
                        print("Cached:", query)
                        continue
                    if attempted:
                        time.sleep(args.delay)
                    attempted += 1
                    try:
                        suggestions = fetch(query, args.timeout)
                        record_fetch(connection, run_id, query, suggestions)
                        print(f"Collected: {query}: {len(suggestions)} suggestions")
                    except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError, OSError) as error:
                        code = error.code if isinstance(error, HTTPError) else None
                        record_fetch(connection, run_id, query, status="error", http_status=code, error=str(error))
                        print(f"Stopped: {query}: {error}")
                        stopped = True
                        break  # No retries, alternate endpoints, or block bypass.
            except KeyboardInterrupt:
                stopped = True
                print("Interrupted; completed fetches retained.")
            finally:
                with connection:
                    connection.execute("UPDATE runs SET finished_at = ?, status = ? WHERE id = ?", (now(), "stopped" if stopped else "complete", run_id))
        export_csv(connection, csv_path)
        total = connection.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
        print(f"Requests: {attempted}; unique stored suggestions: {total}")
        print("Database:", database.resolve())
        print("CSV:", csv_path.resolve())
    finally:
        connection.close()
    return 1 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
