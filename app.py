import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from services.pdf_parser import parse_pdf
from services.quiz_generator import seconds_remaining, shuffle_choices

load_dotenv()
db = SQLAlchemy()
csrf = CSRFProtect()


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=False)
    option_d = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(7), nullable=False)
    category = db.Column(db.String(120), index=True)
    difficulty = db.Column(db.String(40), index=True)
    source_pdf = db.Column(db.String(255), nullable=False)
    page_number = db.Column(db.Integer)
    normalized_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ImportIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_pdf = db.Column(db.String(255), nullable=False)
    page_number = db.Column(db.Integer)
    raw_text = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    resolved = db.Column(db.Boolean, default=False, nullable=False)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', ''),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///quiz.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1',
        SESSION_TYPE='filesystem',
        SESSION_FILE_DIR=os.path.join(app.instance_path, 'sessions'),
        SESSION_PERMANENT=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('Set SECRET_KEY in the environment before starting the application.')
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)
    Session(app)

    with app.app_context():
        db.create_all()
        username, password = os.getenv('ADMIN_USERNAME'), os.getenv('ADMIN_PASSWORD')
        if username and password and not Admin.query.filter_by(username=username).first():
            db.session.add(Admin(username=username, password_hash=generate_password_hash(password)))
            db.session.commit()

    def admin_required(fn):
        from functools import wraps
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('admin_id'):
                return redirect(url_for('login', next=request.path))
            return fn(*args, **kwargs)
        return wrapped

    @app.get('/')
    def index():
        categories = [x[0] for x in db.session.query(Question.category).filter(Question.category.isnot(None)).distinct().all()]
        return render_template('index.html', categories=categories)

    @app.route('/admin/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            admin = Admin.query.filter_by(username=request.form.get('username', '')).first()
            if admin and check_password_hash(admin.password_hash, request.form.get('password', '')):
                session.clear()
                session['admin_id'] = admin.id
                return redirect(request.args.get('next') if request.args.get('next', '').startswith('/') else url_for('dashboard'))
            flash('Invalid username or password.', 'error')
        return render_template('login.html')

    @app.post('/admin/logout')
    @admin_required
    def logout():
        session.clear()
        return redirect(url_for('index'))

    @app.get('/admin')
    @admin_required
    def dashboard():
        search = request.args.get('search', '').strip()
        query = Question.query
        if search:
            pattern = f'%{search}%'
            query = query.filter(or_(Question.question_text.ilike(pattern), Question.category.ilike(pattern), Question.source_pdf.ilike(pattern)))
        questions = query.order_by(Question.created_at.desc()).all()
        issues = ImportIssue.query.filter_by(resolved=False).order_by(ImportIssue.id.desc()).all()
        return render_template('admin/dashboard.html', questions=questions, issues=issues, count=Question.query.count(), search=search)

    @app.post('/admin/upload')
    @app.post('/api/admin/upload-pdf')
    @admin_required
    def upload_pdf():
        upload = request.files.get('pdf')
        if not upload or not upload.filename or not upload.filename.lower().endswith('.pdf'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Choose a PDF file.'}), 400
            flash('Choose a PDF file.', 'error')
            return redirect(url_for('dashboard'))
        data = upload.read()
        if not data.startswith(b'%PDF-'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'The uploaded file is not a valid PDF.'}), 400
            flash('The uploaded file is not a valid PDF.', 'error')
            return redirect(url_for('dashboard'))
        filename = upload.filename.replace('\\', '/').split('/')[-1][:255]
        try:
            parsed, issues = parse_pdf(data)
        except Exception:
            current_app.logger.exception('PDF parsing failed for %s', filename)
            if request.path.startswith('/api/'):
                return jsonify({'error': 'The PDF could not be read.'}), 400
            flash('The PDF could not be read. Try a text-based PDF that opens correctly in a PDF reader.', 'error')
            return redirect(url_for('dashboard'))
        added = duplicates = 0
        for item in parsed:
            digest = item['normalized_hash']
            if Question.query.filter_by(normalized_hash=digest).first():
                duplicates += 1
                continue
            db.session.add(Question(**item, source_pdf=filename, category=request.form.get('category') or None,
                                    difficulty=request.form.get('difficulty') or None))
            added += 1
        # Re-importing the same named PDF refreshes its unresolved parser review items.
        ImportIssue.query.filter_by(source_pdf=filename, resolved=False).delete()
        db.session.add_all([ImportIssue(source_pdf=filename, page_number=i['page_number'], raw_text=i['raw_text'], reason=i['reason']) for i in issues])
        db.session.commit()
        if request.path.startswith('/api/'):
            return jsonify({'imported': added, 'duplicates': duplicates, 'needs_review': len(issues)})
        flash(f'Imported {added} questions; skipped {duplicates} duplicates; {len(issues)} need review.', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/admin/question')
    @admin_required
    def add_question():
        fields = {k: request.form.get(k, '').strip() for k in ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')}
        fields['correct_answer'] = fields['correct_answer'].upper()
        if not all(fields.values()) or fields['correct_answer'] not in 'ABCD':
            flash('Complete the question and all four options, then choose A–D as the answer.', 'error')
            return redirect(url_for('dashboard'))
        from services.pdf_parser import question_hash
        digest = question_hash(fields['question_text'])
        if Question.query.filter_by(normalized_hash=digest).first():
            flash('That question is already in the bank.', 'error')
            return redirect(url_for('dashboard'))
        db.session.add(Question(**fields, normalized_hash=digest, source_pdf='Manual entry', category=request.form.get('category') or None, difficulty=request.form.get('difficulty') or None))
        db.session.commit()
        flash('Question added.', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/admin/question/<int:qid>/delete')
    @admin_required
    def delete_question(qid):
        item = db.get_or_404(Question, qid)
        db.session.delete(item)
        db.session.commit()
        return redirect(url_for('dashboard'))

    @app.post('/admin/questions/delete-all')
    @admin_required
    def delete_all_questions():
        deleted = Question.query.delete(synchronize_session=False)
        db.session.commit()
        flash(f'Deleted all {deleted} questions from the question bank.', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/admin/question/<int:qid>/edit')
    @admin_required
    def edit_question(qid):
        item = db.get_or_404(Question, qid)
        for key in ('question_text', 'option_a', 'option_b', 'option_c', 'option_d'):
            value = request.form.get(key, '').strip()
            if value:
                setattr(item, key, value)
        answer = request.form.get('correct_answer', '').upper().replace(' ', '')
        if answer and set(answer.split(',')).issubset({'A', 'B', 'C', 'D'}):
            item.correct_answer = ','.join(sorted(set(answer.split(','))))
        item.category = request.form.get('category') or None
        difficulty = request.form.get('difficulty') or None
        item.difficulty = difficulty
        from services.pdf_parser import question_hash
        item.normalized_hash = question_hash(item.question_text)
        db.session.commit()
        flash('Question updated.', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/admin/issue/<int:iid>/resolve')
    @admin_required
    def resolve_issue(iid):
        issue = db.get_or_404(ImportIssue, iid)
        issue.resolved = True
        db.session.commit()
        return redirect(url_for('dashboard'))

    @app.post('/admin/issues/delete-unresolved')
    @admin_required
    def delete_unresolved_issues():
        deleted = ImportIssue.query.filter_by(resolved=False).delete(synchronize_session=False)
        db.session.commit()
        flash(f'Removed {deleted} items from the import review queue.', 'success')
        return redirect(url_for('dashboard'))

    @app.get('/api/questions')
    def api_questions():
        query = Question.query
        if request.args.get('category'):
            query = query.filter_by(category=request.args['category'])
        return jsonify([{'id':q.id, 'question':q.question_text, 'category':q.category, 'difficulty':q.difficulty} for q in query.limit(200).all()])

    @app.get('/api/quiz/start')
    def api_start():
        return start_quiz(json_response=True)

    def start_quiz(json_response=False):
        amount = request.values.get('count', '10')
        try:
            amount = min(100, max(1, int(amount)))
        except ValueError:
            amount = 10
        query = Question.query
        if request.values.get('category'):
            query = query.filter_by(category=request.values['category'])
        if request.values.get('difficulty'):
            query = query.filter_by(difficulty=request.values['difficulty'])
        pool = query.order_by(func.random()).limit(amount).all()
        if not pool:
            if json_response:
                return jsonify({'error':'No questions match your selection.'}), 400
            flash('There are no questions matching that selection yet.', 'error')
            return redirect(url_for('index'))
        quiz = []
        for q in pool:
            correct_letters = set(q.correct_answer.split(','))
            choices = [{'label': k, 'text': getattr(q, 'option_'+k.lower()), 'correct': k in correct_letters}
                       for k in 'ABCD' if getattr(q, 'option_'+k.lower())]
            choices = shuffle_choices(choices)
            quiz.append({'id':q.id, 'choices':choices})
        minutes = request.values.get('minutes', '0')
        try:
            minutes = max(0, min(180, int(minutes)))
        except ValueError:
            minutes = 0
        session['quiz'] = {'items':quiz, 'answers':{}, 'current':0, 'started':datetime.now(timezone.utc).timestamp(),
                           'deadline': datetime.now(timezone.utc).timestamp()+minutes*60 if minutes else None}
        if json_response:
            return jsonify({'count':len(quiz), 'url':url_for('quiz')})
        return redirect(url_for('quiz'))

    app.add_url_rule('/quiz/start', 'start_quiz', start_quiz, methods=['POST'])

    @app.get('/quiz')
    def quiz():
        state = session.get('quiz')
        if not state:
            return redirect(url_for('index'))
        items = []
        for item in state['items']:
            q = db.session.get(Question, item['id'])
            if q:
                items.append({'question':q, 'choices':item['choices'], 'answer':state['answers'].get(str(q.id)),
                              'multiple': ',' in q.correct_answer})
        remaining = seconds_remaining(state['deadline'], datetime.now(timezone.utc).timestamp()) if state.get('deadline') else None
        current = min(max(0, int(request.args.get('question', state.get('current', 0)))), max(0, len(items)-1))
        state['current'] = current
        session['quiz'] = state
        return render_template('quiz.html', items=items, current=current, remaining=remaining,
                               answered=sum(bool(value) for value in state['answers'].values()), confirm=request.args.get('confirm') == '1')

    def save_current_quiz_answer():
        state = session.get('quiz')
        if not state:
            return None
        qid = request.form.get('question_id', '')
        if qid in {str(item['id']) for item in state['items']}:
            allowed = next({c['label'] for c in item['choices']} for item in state['items'] if str(item['id']) == qid)
            selected = sorted({value for value in request.form.getlist(qid) if value in allowed})
            state['answers'][qid] = ','.join(selected)
        session['quiz'] = state
        return state

    @app.post('/quiz/navigate')
    def navigate_quiz():
        state = save_current_quiz_answer()
        if not state:
            return redirect(url_for('index'))
        current = min(max(0, int(request.form.get('question', 0))), len(state['items'])-1)
        state['current'] = current
        session['quiz'] = state
        return redirect(url_for('quiz', question=current))

    @app.post('/quiz/confirm')
    def confirm_quiz():
        if not save_current_quiz_answer():
            return redirect(url_for('index'))
        return redirect(url_for('quiz', confirm=1))

    @app.post('/quiz/save')
    def save_quiz():
        state = session.get('quiz')
        if not state:
            return jsonify({'error': 'No active quiz.'}), 400
        allowed = {str(item['id']): {c['label'] for c in item['choices']} for item in state['items']}
        incoming = request.form
        for qid, choices in allowed.items():
            values = [v for v in request.form.getlist(qid) if v in choices]
            if values:
                state['answers'][qid] = ','.join(sorted(set(values)))
        session['quiz'] = state
        return jsonify({'saved': True})

    @app.post('/api/quiz/submit')
    @app.post('/quiz/submit')
    def submit_quiz():
        state = session.get('quiz')
        if not state:
            return jsonify({'error':'No active quiz.'}), 400
        answers = state['answers']
        incoming = request.get_json(silent=True) if request.is_json else request.form
        for item in state['items']:
            qid = str(item['id'])
            values = request.form.getlist(qid) if not request.is_json else ((incoming or {}).get(qid, []) if isinstance((incoming or {}).get(qid, []), list) else [(incoming or {}).get(qid)])
            allowed = {c['label'] for c in item['choices']}
            selected = sorted({v for v in values if v in allowed})
            if selected:
                answers[qid] = ','.join(selected)
        total = correct = 0
        review = []
        for item in state['items']:
            q = db.session.get(Question, item['id'])
            if not q: continue
            picked = answers.get(str(q.id))
            picked_letters = set(picked.split(',')) if picked else set()
            correct_letters = {c['label'] for c in item['choices'] if c['correct']}
            is_correct = picked_letters == correct_letters and bool(correct_letters)
            total += 1
            correct += int(is_correct)
            review.append({'question':q.question_text, 'selected':picked, 'answer':q.correct_answer,
                           'answer_text':', '.join(getattr(q,'option_'+letter.lower()) for letter in q.correct_answer.split(',')),
                           'selected_text':', '.join(getattr(q,'option_'+letter.lower()) for letter in picked.split(',')) if picked else 'No answer', 'correct':is_correct})
        elapsed = max(0, int(datetime.now(timezone.utc).timestamp()-state['started']))
        result = {'total':total, 'correct':correct, 'incorrect':total-correct, 'percentage':round(100*correct/total) if total else 0,
                  'grade':'A' if total and correct/total >= .9 else 'B' if total and correct/total >= .8 else 'C' if total and correct/total >= .7 else 'D' if total and correct/total >= .6 else 'F',
                  'seconds':elapsed, 'review':review}
        session.pop('quiz', None)
        session['result'] = result
        if request.is_json:
            return jsonify(result)
        return redirect(url_for('result'))

    @app.get('/api/quiz/result/')
    @app.get('/quiz/result')
    def result():
        value = session.get('result')
        if not value:
            return redirect(url_for('index'))
        return render_template('result.html', result=value)

    return app


if __name__ == '__main__':
    create_app().run(debug=os.getenv('FLASK_DEBUG') == '1')
