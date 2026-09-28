from services.scoring import score_answers


def test_scores_unanswered_as_incorrect():
    result = score_answers({'one':'A', 'two':'C'}, {'one':'A'})
    assert result == {'total':2, 'correct':1, 'incorrect':1, 'percentage':50, 'grade':'F'}
