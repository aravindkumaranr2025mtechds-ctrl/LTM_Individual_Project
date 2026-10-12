"""ABB terminal workflow: symptom search, exact selection, scoped assistance.

Session state is in memory. No extra dependencies; calls the local FastAPI app.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8000'
PREFIX = 'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
STORE = PREFIX + '_structured_v1_ready_bge_small.npz'
INDEX = PREFIX + '_structured_v1_ready_evidence_v1.json'


def post_api(path, payload):
    request = Request(
        BASE + path, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urlopen(request, timeout=120 if path == '/documents/search/abb' else 30) as response:
        return json.load(response)


def run_assistant(post=None, read=None, write=None):
    post = post_api if post is None else post
    read = input if read is None else read
    write = print if write is None else write

    def choose(prompt, allowed):
        while True:
            value = read(prompt).strip().lower()
            if value in allowed:
                return value
            write('Choose one of: ' + ', '.join(allowed))

    write('ABB DEVELOPMENT ASSISTANT')
    write('Manufacturer source information and unreviewed report checks; no fault diagnosis.')
    write('Use one machine and observation interval. This script does not save session answers.')

    while True:
        query = read('\nSTEP 1 - Describe the motor symptom (q to exit): ').strip()
        if query.lower() == 'q':
            return None
        if not query:
            write('Enter a symptom description.')
            continue
        routed = post('/documents/search/abb', {
            'vector_store_filename': STORE, 'query': query, 'top_k': 5,
        })
        if routed.get('document_id') != PREFIX:
            raise ValueError('Search response does not match the configured ABB document.')
        options = (routed.get('clarification') or {}).get('options') or routed.get('symptom_candidates', [])
        if not options and routed.get('selected_symptom_id'):
            options = [{'symptom_id': routed['selected_symptom_id'], 'symptom': routed['selected_symptom']}]
        if not options:
            write('No symptom options returned. Try a clearer description.')
            continue
        for number, option in enumerate(options, 1):
            write(f"S{number} = {option['symptom']}")
        write('N = None matches; describe again. Q = Exit.')
        selection = choose('STEP 1 - Select a symptom using S1, S2, etc.: ', ['n', 'q'] + ['s' + str(n) for n in range(1, len(options) + 1)])
        if selection == 'q':
            return None
        if selection == 'n':
            continue
        selected = options[int(selection[1:]) - 1]
        confirmed = post('/documents/search/abb/confirm', {
            'vector_store_filename': STORE, 'symptom_id': selected['symptom_id'], 'top_k': 10,
        })
        if (confirmed.get('status') != 'confirmed_selection'
                or confirmed.get('document_id') != PREFIX
                or confirmed.get('selected_symptom_id') != selected['symptom_id']):
            raise ValueError('Exact symptom confirmation failed. No fallback was used.')
        write('\nSelected symptom: ' + confirmed['selected_symptom'])
        write('Source: ' + confirmed['source_filename'])
        break

    if selected['symptom_id'] != PREFIX + '_s002':
        write('Report review currently covers Motor stalls. Source records for this symptom:')
        for item in confirmed['results']:
            write(f"  {item['possible_cause']} | page(s) {item['page_numbers']}")
        if confirmed.get('has_more'):
            write('Additional source records exist; this list is incomplete.')
        return confirmed

    write('L = List possible causes from the manual')
    write('R = Review existing reports and answer clarification questions')
    write('D = Ask whether an actual cause can be identified')
    write('q = Exit')
    choice = choose('STEP 2 - Choose L, R, or D: ', ['l', 'r', 'd', 'q'])
    if choice == 'q':
        return None
    task = {'l': 'list_possible_causes', 'r': 'review_reports', 'd': 'identify_cause'}[choice]
    observations, deferred = {}, []
    confirmed_causes = {r['record_id']: r['possible_cause'] for r in confirmed['results']}
    while True:
        result = post('/development/abb/stall/assist', {
            'index_filename': INDEX, 'requested_information': task,
            'observations': observations, 'deferred_fact_ids': deferred,
        })
        source_causes = {r['record_id']: r['possible_cause'] for r in result['source_records']}
        if source_causes != confirmed_causes:
            raise ValueError('Confirmed retrieval and assistance source records differ. Review source versions.')
        write('\nStatus: ' + result['status'])
        if task == 'list_possible_causes':
            for item in result['source_records']:
                write(f"  {item['possible_cause']} | page(s) {item['page_numbers']}")
        if result['report_assessment'] is not None:
            for item in result['report_assessment']:
                write(f"  {item['possible_cause']}: {item['status']}")
        clarification = result['clarification']
        if not clarification or clarification['question'] is None:
            write(result['message'])
            return result
        question = clarification['question']
        write('\n' + question['text'])
        write('Evidence: ' + question['evidence_id'])
        write('P = Reported present; A = Reported absent; U = Cannot clarify now; Q = Exit')
        answer = choose('STEP 3 - Report P, A, or U: ', ['p', 'a', 'u', 'q'])
        if answer == 'q':
            return None
        fact = question['fact_id']
        if answer == 'u':
            if fact not in deferred:
                deferred.append(fact)
        else:
            observations[fact] = [answer == 'p']
            if fact in deferred:
                deferred.remove(fact)


if __name__ == '__main__':
    try:
        run_assistant()
    except HTTPError as error:
        print(f'API error {error.code}: {error.read().decode("utf-8", errors="replace")}')
        raise SystemExit(1)
    except (URLError, TimeoutError) as error:
        print('Local API unavailable or timed out. Check the backend terminal and port 8000.')
        print(str(error))
        raise SystemExit(1)
    except (ValueError, KeyError, TypeError) as error:
        print('Response could not be used:', error)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nSession ended.')

