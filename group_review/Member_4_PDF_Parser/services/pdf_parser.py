"""Best-effort parser for common numbered multiple-choice PDF layouts."""
import hashlib
import io
import re
import unicodedata

import pymupdf as fitz

QUESTION_START = re.compile(r'^\s*(?:Q(?:uestion)?\s*)?(\d{1,4})\s*[.)\-:]\s*(.*)$', re.I)
OPTION_START = re.compile(r'^\s*([A-D])\s*[.)]\s*(.*)$', re.I)
ANSWER = re.compile(r'^\s*(?:correct\s*)?(?:answers?|ans)\s*[:\-]?\s*([A-D](?:\s*[,/&]\s*[A-D])*)\b', re.I)


def question_hash(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = re.sub(r'[^\w]+', ' ', normalized, flags=re.UNICODE).strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def parse_pdf(data):
    """Return (validated question dicts, review issue dicts), retaining source page."""
    doc = fitz.open(stream=data, filetype='pdf')
    questions, issues, chunks = [], [], []
    current = None
    in_answer_key = False
    for page_no, page in enumerate(doc, 1):
        for line in page.get_text('text').splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r'^(?:answer\s*key|answers)\s*:?\s*$', line, re.I):
                in_answer_key = True
                continue
            if in_answer_key:
                continue
            match = QUESTION_START.match(line)
            if match:
                if current:
                    chunks.append(current)
                current = {'page_number':page_no, 'text':[match.group(2).strip()], 'options':{}, 'answer':None, 'raw':[line]}
                continue
            if current is None:
                continue
            current['raw'].append(line)
            ans = ANSWER.match(line)
            if ans:
                current['answer'] = ','.join(sorted(set(re.findall(r'[A-D]', ans.group(1).upper()))))
                continue
            opt = OPTION_START.match(line)
            if opt:
                current['options'][opt.group(1).upper()] = opt.group(2).strip()
            elif current['options']:
                last = list(current['options'])[-1]
                current['options'][last] += ' ' + line
            else:
                current['text'].append(line)
    if current:
        chunks.append(current)

    # Answer keys commonly appear as "1. B  2. C" after the questions.
    full_text = '\n'.join(p.get_text('text') for p in doc)
    key_match = re.search(r'(?:answer\s*key|answers)\s*[:\n]+([\s\S]{0,10000})', full_text, re.I)
    answer_key = {}
    if key_match:
        answer_key = {int(n): a.upper() for n, a in re.findall(r'(\d{1,4})\s*[.)\-:]?\s*([A-D])\b', key_match.group(1), re.I)}

    seen = set()
    for chunk in chunks:
        text = re.sub(r'\s+', ' ', ' '.join(chunk['text'])).strip()
        answer = chunk['answer']
        # Number comes from each source header; try recovering it for answer key lookup.
        if not answer:
            for raw_line in chunk['raw'][:1]:
                m = QUESTION_START.match(raw_line)
                if m:
                    answer = answer_key.get(int(m.group(1)))
        options = chunk['options']
        true_false = (options.get('A', '').strip().casefold() == 'true' and
                      options.get('B', '').strip().casefold() == 'false' and
                      set(options).issubset({'A', 'B'}))
        if true_false:
            options['C'] = options['D'] = ''
        correct = set(answer.split(',')) if answer else set()
        reason = None
        if not text: reason = 'Question text is missing.'
        elif any(k not in options or not options[k].strip() for k in ('A', 'B') if true_false): reason = 'True/false options are missing.'
        elif not true_false and any(k not in options or not options[k].strip() for k in 'ABCD'): reason = 'One or more A–D options are missing.'
        elif not correct or not correct.issubset(set(options)): reason = 'Correct answer is missing or does not match the available options.'
        if reason:
            issues.append({'page_number':chunk['page_number'], 'raw_text':'\n'.join(chunk['raw']), 'reason':reason})
            continue
        digest = question_hash(text)
        if digest in seen:
            continue
        seen.add(digest)
        questions.append({'question_text':text, **{'option_'+k.lower():options[k] for k in 'ABCD'},
                          'correct_answer':answer, 'page_number':chunk['page_number'], 'normalized_hash':digest})
    return questions, issues
