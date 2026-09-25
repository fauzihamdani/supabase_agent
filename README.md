# Supabase Read-Only Data Agent (LangGraph + Groq)

Agent yang menerima pertanyaan bahasa natural, menerjemahkannya jadi query
read-only ke tabel `projects` di Supabase, dan bisa export hasilnya ke `.xlsx`.
Didesain sebagai backend yang dipanggil dari Next.js.

## Struktur

```
database.py   -> koneksi read-only ke Supabase Postgres (SQLAlchemy)
tools.py      -> tool query_projects (satu-satunya cara agent akses data)
agent.py      -> LangGraph graph: router (guardrail) -> agent (Groq+tools) -> tools
export.py     -> export list hasil ke file .xlsx
server.py     -> FastAPI, endpoint untuk dipanggil dari Next.js
sql/create_readonly_role.sql -> bikin role Postgres khusus SELECT
```

## Keamanan read-only (2 lapis)

1. **DB-level**: jalankan `sql/create_readonly_role.sql` di Supabase SQL editor
   untuk bikin role `readonly_agent` yang cuma punya `GRANT SELECT`. Pakai
   connection string role ini di `SUPABASE_DB_URL` — JANGAN pakai `service_role`
   atau user `postgres`.
2. **App-level**: `tools.py` hanya menyusun query `SELECT ... WHERE ...` dengan
   parameter ter-bind (bukan raw SQL dari LLM), dan `database.py` set
   `SET TRANSACTION READ ONLY` di setiap koneksi.

LLM tidak pernah diberi akses untuk menulis SQL bebas — dia hanya bisa
memanggil tool `query_projects(search, status, member_id, date_from, date_to, limit)`.

## Guardrail anti-halusinasi

- Node `router` di `agent.py` mengklasifikasi setiap pesan: `DATA_QUERY` atau `OTHER`.
  Kalau `OTHER`, agent langsung menolak dengan pesan tetap, tidak memanggil LLM utama.
- System prompt melarang keras menjawab dari ingatan; semua fakta harus datang dari
  hasil tool.

## Instalasi

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# isi .env: GROQ_API_KEY, SUPABASE_DB_URL, dst
```

Jalankan SQL role read-only di Supabase dashboard (SQL Editor) memakai isi
`sql/create_readonly_role.sql` (ganti password).

## Menjalankan server

```bash
uvicorn server:app --reload --port 8000
```

## Endpoint untuk Next.js

- `POST /chat` — body: `{"message": "cari project status active bulan ini"}`
  balasan: `{"reply": "...", "tool_results": [ ... data project ... ]}`
- `POST /projects/filter` — body sesuai UI filter kamu:
  ```json
  {"search": "chatbot", "status": "active", "member_id": "uuid...", "date_from": "2026-01-01", "date_to": "2026-12-31"}
  ```
  balasan: array JSON data project (tanpa lewat LLM, cepat & deterministik — cocok
  untuk tabel utama di FE, bukan chat).
- `POST /projects/export` — body sama seperti `/projects/filter`, balasan file `.xlsx`
  langsung (FE tinggal trigger download dari response ini).

## Contoh pemakaian dari Next.js

```ts
// filter biasa (tabel)
const res = await fetch("http://localhost:8000/projects/filter", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ search: "chatbot", status: "active" }),
});
const data = await res.json();

// export ke xlsx
const res2 = await fetch("http://localhost:8000/projects/export", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ status: "active" }),
});
const blob = await res2.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement("a");
a.href = url; a.download = "projects.xlsx"; a.click();

// chat natural language
const res3 = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "project apa saja yang deadline bulan depan?" }),
});
```

## Catatan

- Kolom `member` di contoh data cuma UUID (`assigned_to`). Kalau kamu punya tabel
  `profiles`/`users` untuk nama anggota, kasih tahu strukturnya — tinggal tambah
  JOIN di `tools.py` dan grant SELECT tabel itu juga di role read-only.
- Model default `llama-3.3-70b-versatile` di Groq — ganti di `.env` (`GROQ_MODEL`)
  kalau mau pakai model Groq lain.
