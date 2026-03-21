# AutoPASS Toll Management System

A full-stack web application simulating a modern Norwegian toll road system (bompengeselskap). Built with a focus on
backend architecture, database-driven business logic, and security.

## ✅ Features

- **Secure Authentication** — Registration and login with bcrypt password hashing, JWT tokens stored in HTTP-only
  cookies (XSS protection)
- **Dynamic Pricing Engine** — Rush-hour surcharges (×1.2 at 07:00–08:30 and 15:30–17:00) and fuel-type discounts
  calculated entirely in a SQL VIEW
- **Vehicle Management** — Register vehicles with AutoPASS agreements; IDOR protection prevents users from accessing
  other users' data via URL manipulation
- **Passage Tracking** — Full transaction log with per-vehicle and per-month filtering
- **Finances Page** — Monthly cost aggregation with eco-saving bonus calculation, powered by SQL `GROUP BY`
- **PDF Export** — Download trip reports and monthly pre-invoices generated in-memory (no server-side file storage)
- **Async Caching** — `async_lru` caching on heavy database queries with cache invalidation on write operations
- **Structured Logging** — Warning/error logging to file with no sensitive data exposure

## 🛠️ Tech Stack

| Layer      | Technology                                                 |
|------------|------------------------------------------------------------|
| Backend    | Python 3.11+, FastAPI                                      |
| Database   | SQLite3 via `aiosqlite` (async)                            |
| Validation | Pydantic v2 (`field_validator`, `model_validator`, `Enum`) |
| Frontend   | Jinja2, HTML5, CSS3, Bootstrap 5, JavaScript               |
| Auth       | JWT (`PyJWT`), bcrypt (`werkzeug.security`)                |
| PDF        | `fpdf2`                                                    |
| Caching    | `async-lru`                                                |

## 🗄️ Database Architecture

Business logic is offloaded to the database layer:

- **`GENERATED ALWAYS AS` columns** — Discount percentages computed and stored automatically based on fuel type
- **VIEW (`all_passages`)** — Calculates final toll price using `strftime`-based rush-hour logic
  (×1.2 surcharge at 07:00–08:30 and 15:30–17:00) combined with per-vehicle fuel discounts.
  No Python involved — pure SQL math.
- **Computed columns** (`GENERATED ALWAYS AS STORED`) — Discount percentages calculated and
  stored at the database level, not in application code.
- **Trigger (`register_unknown_car`)** — Automatically registers unknown vehicles on first passage, preventing crashes
- **Indexes** — On `passed_at` and `station_id` for query performance
- **Prices stored as integers (øre)** — Avoids floating-point rounding errors; standard practice in financial systems

## ⚙️ Local Setup

```bash
git clone https://github.com/SHS34S0/autopass-toll-system.git
cd autopass-toll-system

pip install -r requirements.txt

cp config.py.example config.py
# Edit config.py and set your SECRET_KEY

fastapi dev main.py
```

The database is created automatically on first run from `db/schema.sql`.

## 🔐 Security Notes

- Passwords are never stored in plaintext — bcrypt hashing with unique salts
- JWT stored in HTTP-only cookie, not accessible via JavaScript
- All database queries use parameterized placeholders — no string concatenation
- IDOR protection on `/dashboard/{car_num}` — ownership verified before data is returned
- Email uniqueness enforced at the database constraint level (`IntegrityError` handling, EAFP pattern)