from services.quiz_generator import seconds_remaining, shuffle_choices


def test_shuffle_preserves_every_choice_and_answer_marker():
    choices = [{'label': 'A', 'correct': True}, {'label': 'B', 'correct': False},
               {'label': 'C', 'correct': False}, {'label': 'D', 'correct': False}]
    shuffled = shuffle_choices(choices)
    assert {c['label'] for c in shuffled} == {'A', 'B', 'C', 'D'}
    assert [c['label'] for c in shuffled if c['correct']] == ['A']


def test_countdown_uses_absolute_deadline_after_refresh():
    assert seconds_remaining(130, 100) == 30
    assert seconds_remaining(130, 131) == 0
