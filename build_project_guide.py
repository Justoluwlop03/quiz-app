"""Build a readable PDF overview of the Quizbank project using PyMuPDF."""
from pathlib import Path

import pymupdf as fitz


OUT = Path(__file__).with_name("Quizbank_Project_Guide.pdf")
PAGE_W, PAGE_H = 595, 842
MARGIN = 54
INK = (0.12, 0.17, 0.24)
MUTED = (0.36, 0.42, 0.49)
TEAL = (0.08, 0.48, 0.48)
PALE = (0.91, 0.96, 0.95)
LINE = (0.86, 0.89, 0.91)

doc = fitz.open()
page = None
y = 0
page_no = 0


def new_page(title="Quizbank | Project guide"):
    global page, y, page_no
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page_no += 1
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 9), color=TEAL, fill=TEAL)
    page.insert_text((MARGIN, 35), "QUIZBANK  /  PROJECT GUIDE", fontsize=8,
                     fontname="hebo", color=TEAL)
    page.draw_line((MARGIN, 47), (PAGE_W - MARGIN, 47), color=LINE, width=0.7)
    page.draw_line((MARGIN, PAGE_H - 42), (PAGE_W - MARGIN, PAGE_H - 42), color=LINE, width=0.7)
    page.insert_text((MARGIN, PAGE_H - 25), "Flask • Python • PyMuPDF", fontsize=8,
                     fontname="helv", color=MUTED)
    page.insert_text((PAGE_W - MARGIN - 28, PAGE_H - 25), f"{page_no:02d}", fontsize=8,
                     fontname="helv", color=MUTED)
    y = 76
    if title:
        heading(title, 22)


def ensure(height):
    global y
    if y + height > PAGE_H - 60:
        new_page()


def wrapped(text, size, width, font="helv"):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if current and fitz.get_text_length(test, fontname=font, fontsize=size) > width:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def heading(text, size=17):
    global y
    ensure(size + 24)
    page.insert_text((MARGIN, y + size), text, fontsize=size, fontname="hebo", color=INK)
    y += size + 14


def paragraph(text, size=10.3, color=INK, indent=0, font="helv", gap=7):
    global y
    width = PAGE_W - 2 * MARGIN - indent
    lines = wrapped(text, size, width, font)
    line_h = size * 1.48
    ensure(len(lines) * line_h + gap)
    for line in lines:
        page.insert_text((MARGIN + indent, y + size), line, fontsize=size, fontname=font, color=color)
        y += line_h
    y += gap


def bullet(label, text):
    global y
    width = PAGE_W - 2 * MARGIN - 20
    lines = wrapped(f"{label} — {text}", 10, width)
    line_h = 14.4
    ensure(len(lines) * line_h + 4)
    page.draw_circle((MARGIN + 4, y + 7), 2.2, color=TEAL, fill=TEAL)
    for i, line in enumerate(lines):
        page.insert_text((MARGIN + 15, y + 10 + i * line_h), line, fontsize=10,
                         fontname="helv", color=INK)
    y += len(lines) * line_h + 4


def callout(title, body):
    global y
    lines = wrapped(body, 9.5, PAGE_W - 2 * MARGIN - 28)
    h = 28 + len(lines) * 14
    ensure(h + 10)
    rect = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + h)
    page.draw_rect(rect, color=PALE, fill=PALE)
    page.insert_text((MARGIN + 14, y + 18), title, fontsize=9, fontname="hebo", color=TEAL)
    for i, line in enumerate(lines):
        page.insert_text((MARGIN + 14, y + 34 + i * 14), line, fontsize=9.5,
                         fontname="helv", color=INK)
    y += h + 12


# Cover
new_page("")
y = 150
page.insert_text((MARGIN, y), "PROJECT EXPLAINER", fontsize=10, fontname="hebo", color=TEAL)
y += 48
page.insert_text((MARGIN, y), "Quizbank", fontsize=38, fontname="hebo", color=INK)
y += 32
paragraph("A Python web application that turns text-based PDF question banks into searchable quizzes, timed practice sessions, and instant answer reviews.",
          size=15, color=MUTED, gap=25)
callout("IN ONE SENTENCE", "An administrator imports and curates questions; a learner chooses a quiz, answers shuffled choices, and receives a score with explanations of the correct choices.")
heading("What this guide covers", 15)
for label, text in [
    ("Purpose", "The app’s two user roles and the main journey through it."),
    ("Implementation", "The responsibilities of app.py and the services package."),
    ("Python concepts", "The language features and programming patterns demonstrated by the code."),
    ("Practical notes", "Storage, security choices, limits, and how to run the application."),
]:
    bullet(label, text)
paragraph("Based on the project source in this folder. The central implementation is app.py, with PDF parsing, quiz helpers, and scoring in services/.",
          size=9, color=MUTED, gap=0)

# Product flow
new_page("1. What the application does")
paragraph("Quizbank is a small learning platform. It has an administrator workflow for building the question library and a learner workflow for practicing from that library.")
heading("Administrator workflow", 14)
for label, text in [
    ("Sign in", "An admin account is initialized from environment settings; passwords are stored as hashes."),
    ("Add content", "Upload a PDF or enter a question manually. Imported questions can be tagged with a category and difficulty."),
    ("Review", "Questions that do not fit the parser’s expected structure are saved in an import review queue with their source page and extracted text."),
    ("Maintain", "Search, edit, resolve review items, or delete questions from the dashboard."),
]: bullet(label, text)
heading("Learner workflow", 14)
for label, text in [
    ("Choose", "Select the question count, category, difficulty, and optional timer."),
    ("Practice", "The server randomly selects questions, shuffles their choices, and stores quiz progress in the session."),
    ("Submit", "Answers are checked against the correct answer set; unanswered items count as incorrect."),
    ("Learn", "The result page shows the percentage, grade, elapsed time, and answer-by-answer review."),
]: bullet(label, text)
callout("IMPORTANT PDF LIMIT", "The parser extracts selectable text from PDFs. Image-only scans require OCR before upload, and unusual layouts may need manual review.")

# Architecture
new_page("2. How the code is organized")
heading("Main pieces", 14)
for label, text in [
    ("app.py", "Creates the Flask app, configures extensions, defines database models, and registers web pages and JSON API routes."),
    ("services/pdf_parser.py", "Reads PDF text, detects question and answer patterns, validates options, records issues, and creates duplicate-detection hashes."),
    ("services/quiz_generator.py", "Contains small helpers for shuffling answer choices and calculating remaining time."),
    ("services/scoring.py", "Provides a reusable scoring helper. The main submission route also builds detailed answer review data."),
    ("templates/", "Jinja HTML templates render the home page, admin pages, quiz, and results; static/ contains CSS."),
    ("tests/", "Tests cover PDF parsing, quiz helpers, scoring, and admin authentication."),
]: bullet(label, text)
heading("Request and data flow", 14)
for label, text in [
    ("Upload", "A Flask route checks the file, passes its bytes to parse_pdf, then saves valid Question rows and ImportIssue rows."),
    ("Persist", "Flask-SQLAlchemy maps Python model classes to relational tables. SQLite is the default; DATABASE_URL can point at PostgreSQL."),
    ("Start quiz", "A route filters and randomly selects database rows, shuffles choices, then stores question IDs and answers in the server-side session."),
    ("Render and submit", "Routes pass model data to Jinja templates. Submission computes correctness and stores the result in the session for the result page."),
]: bullet(label, text)
callout("ROUTES", "The app serves both browser pages and JSON endpoints: for example /quiz/start and /api/quiz/start share quiz creation logic, while /api/quiz/submit returns JSON when the request is JSON.")

# Functions
new_page("3. Important functions and logic")
heading("Application setup and routes", 14)
for label, text in [
    ("create_app(test_config=None)", "Builds the Flask application, loads settings, initializes SQLAlchemy, CSRF protection, and server-side sessions, creates tables, and registers routes. Passing test_config supports isolated test settings."),
    ("admin_required(fn)", "A decorator checks for an admin ID in the session and redirects unauthenticated requests to sign-in."),
    ("upload_pdf()", "Validates the extension and PDF signature, parses uploaded bytes, skips known hashes, and stores valid questions and import issues."),
    ("start_quiz()", "Clamps user inputs to safe ranges, applies filters, selects random questions, and saves a quiz state with an optional deadline."),
    ("submit_quiz()", "Accepts form or JSON answers, filters selections to allowed choice labels, compares answer sets, computes a grade, and prepares review data."),
]: bullet(label, text)
heading("PDF parser", 14)
for label, text in [
    ("parse_pdf(data)", "Opens PDF bytes with PyMuPDF, walks pages and lines, groups text into question chunks, recognizes options and answers, validates each chunk, and returns (questions, issues)."),
    ("question_hash(text)", "Normalizes Unicode, case, and punctuation, then computes a SHA-256 digest. The database’s unique hash constraint helps prevent duplicate imports."),
    ("Pattern matching", "Regular expressions recognize numbered question headings, A–D options, inline answer labels, and a trailing answer key."),
]: bullet(label, text)
heading("Small helper functions", 14)
paragraph("shuffle_choices(options, rng=None) copies and shuffles a list, with an optional random-number generator for repeatable tests. seconds_remaining(deadline, now) returns a nonnegative countdown. score_answers(correct_by_question, selected_by_question) counts correct, incorrect, percentage, and letter grade.")
callout("MULTIPLE ANSWERS", "Answers are stored as comma-separated letters and compared as sets, so a multiple-select question is correct only when the selected set exactly matches the correct set.")

# Python concepts
new_page("4. Python concepts this project uses")
for label, text in [
    ("Functions and modules", "Related behavior is split into functions and services modules. Imports connect the Flask app to parsing and quiz helpers."),
    ("Classes and object-relational mapping", "Admin, Question, and ImportIssue are Python classes that SQLAlchemy maps to database tables; columns define data types, constraints, and indexes."),
    ("Decorators", "@app.get, @app.post, and @app.route register URL handlers. @admin_required wraps views to add a sign-in check."),
    ("Data structures", "Dictionaries represent questions, choices, quiz state, and results; lists preserve ordered collections; sets make answer comparison and de-duplication straightforward."),
    ("Comprehensions and iteration", "List, set, and dictionary comprehensions transform database rows and form data compactly. Loops process PDF lines, quiz items, and selected answers."),
    ("Error handling and validation", "try/except handles malformed numeric input and PDF parsing failures. Explicit checks validate upload type, required fields, answer labels, and quiz bounds."),
    ("Text processing", "Regular expressions parse semi-structured PDF text. Unicode normalization and case folding make question hashes less sensitive to formatting."),
    ("Time and state", "Timezone-aware UTC timestamps measure elapsed time and deadlines. Flask sessions keep quiz progress across requests."),
    ("Web application patterns", "HTTP methods separate reads from changes; routes use redirects and flash messages for browser flows, and JSON responses for API flows."),
    ("Configuration from the environment", "python-dotenv loads local settings, while environment variables configure secrets, database URLs, upload limits, and cookie behavior."),
]: bullet(label, text)

# Technical detail
new_page("5. Data, dependencies, and safeguards")
heading("Stored records", 14)
for label, text in [
    ("Admin", "Unique username and a password hash. Werkzeug’s password helpers verify credentials without storing plain-text passwords."),
    ("Question", "Question text, four options, correct answer letters, category, difficulty, source PDF, page number, normalized hash, and creation time."),
    ("ImportIssue", "Source file, page, raw extracted text, reason for rejection, and whether the item was reviewed."),
]: bullet(label, text)
heading("Main packages", 14)
for label, text in [
    ("Flask", "HTTP routing, request handling, templates, sessions, redirects, and messages."),
    ("Flask-SQLAlchemy / SQLAlchemy", "Database models, queries, and persistence."),
    ("Flask-WTF", "CSRF protection for submitted forms."),
    ("Flask-Session", "Server-side session storage for quiz state."),
    ("PyMuPDF", "Text extraction from uploaded PDFs."),
    ("python-dotenv", "Local environment-file configuration."),
]: bullet(label, text)
heading("Safeguards visible in the code", 14)
paragraph("The application requires SECRET_KEY at startup, hashes admin passwords, limits upload size, checks that uploads begin with a PDF signature, protects forms with CSRF, uses HttpOnly and SameSite session cookies, and can set Secure cookies behind HTTPS with COOKIE_SECURE=1. Admin routes check session identity.")
callout("DEPLOYMENT NOTE", "The README recommends setting a strong SECRET_KEY and changing admin credentials. For production, configure DATABASE_URL and HTTPS cookie settings; the default local database is SQLite.")

# Run & boundaries
new_page("6. Running it and understanding its limits")
heading("Local setup", 14)
for label, text in [
    ("1", "Use Python 3.10 or newer and create a virtual environment."),
    ("2", "Install the packages listed in requirements.txt."),
    ("3", "Copy .env.example to .env; set SECRET_KEY and admin credentials."),
    ("4", "Run flask --app app:create_app run from the project directory."),
    ("5", "Sign in at /admin/login, upload a PDF or add questions by hand, then start a quiz from the home page."),
]: bullet(label, text)
heading("Current scope and constraints", 14)
for label, text in [
    ("PDF format", "The parser targets common numbered multiple-choice layouts. It is best-effort, not a general-purpose exam-document understanding system."),
    ("Scanned documents", "Image-only pages do not provide text for the current parser; OCR is needed first."),
    ("Duplicate policy", "The question text hash ignores case, Unicode compatibility differences, and punctuation. Two distinct questions with identical normalized text may be treated as duplicates."),
    ("Quiz persistence", "Answers are held in a server-side session, not stored as permanent learner history in the database."),
    ("Timer behavior", "The server computes a deadline and exposes remaining time at page render; this code does not automatically submit an expired quiz."),
    ("Manual edits", "Editing a question recalculates its normalized hash, which is protected by a unique database constraint."),
]: bullet(label, text)
callout("PROJECT SUMMARY", "Quizbank combines practical web development with core Python skills: parsing imperfect text, modeling data, validating input, managing session state, and turning stored records into an interactive study workflow.")

doc.set_metadata({
    "title": "Quizbank Project Guide",
    "author": "Quizbank project overview",
    "subject": "Application purpose, Python concepts, architecture, and operation",
})
doc.save(OUT, garbage=4, deflate=True)
print(f"Created {OUT} ({len(doc)} pages)")
