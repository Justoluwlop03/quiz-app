def score_answers(correct_by_question, selected_by_question):
    """Score a mapping of question id to answer letter; unanswered questions are wrong."""
    total = len(correct_by_question)
    correct = sum(selected_by_question.get(qid) == answer for qid, answer in correct_by_question.items())
    pct = round(correct * 100 / total) if total else 0
    grade = 'A' if total and pct >= 90 else 'B' if total and pct >= 80 else 'C' if total and pct >= 70 else 'D' if total and pct >= 60 else 'F'
    return {'total': total, 'correct': correct, 'incorrect': total-correct, 'percentage': pct, 'grade': grade}
