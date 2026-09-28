# Quizbank

A Flask application that imports multiple choice questions dynamically from PDF files. Questions retain their PDF filename and page number, while normalized text hashes prevent duplicate imports.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment, then install `requirements.txt`.
3. Copy `.env.example` to `.env`, set a long random `SECRET_KEY`, and change the admin password.
4. Run `flask --app app:create_app run` from this folder. The SQLite database and server-side sessions are created under `instance/`.
5. Sign in at `/admin/login`, upload a PDF, review any failed extractions, then create a quiz from the home page.

Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL for production. Set `COOKIE_SECURE=1` when serving over HTTPS. This parser handles text-based PDFs; scanned image-only PDFs need OCR before import.

## Tests

Run `pytest` to execute the parser and scoring tests. The parser tests generate small sample PDFs at runtime, so no question bank is hardcoded into the application.
