import io

import pymupdf as fitz

from services.pdf_parser import parse_pdf, question_hash


def make_pdf(text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_extracts_options_answer_and_page():
    data = make_pdf('''1. Which planet is known as the Red Planet?\nA. Earth\nB. Mars\nC. Venus\nD. Jupiter\nCorrect Answer: B''')
    questions, issues = parse_pdf(data)
    assert not issues
    assert len(questions) == 1
    assert questions[0]['option_b'] == 'Mars'
    assert questions[0]['correct_answer'] == 'B'
    assert questions[0]['page_number'] == 1


def test_marks_missing_answer_for_review():
    data = make_pdf('''1) Select a color\nA) Red\nB) Blue\nC) Green\nD) Yellow''')
    questions, issues = parse_pdf(data)
    assert not questions
    assert len(issues) == 1
    assert 'answer' in issues[0]['reason'].lower()


def test_normalized_question_hash_ignores_punctuation_and_case():
    assert question_hash('What is 2+2?') == question_hash(' WHAT IS 2 + 2 ')


def test_imports_true_false_and_multi_select_answers():
    data = make_pdf('''1. Statement\nA. True\nB. False\nCorrect Answer: B\n2. Select all\nA. Alpha\nB. Beta\nC. Gamma\nD. Delta\nCorrect Answers: A, C''')
    questions, issues = parse_pdf(data)
    assert not issues
    assert questions[0]['correct_answer'] == 'B'
    assert questions[0]['option_c'] == ''
    assert questions[1]['correct_answer'] == 'A,C'
