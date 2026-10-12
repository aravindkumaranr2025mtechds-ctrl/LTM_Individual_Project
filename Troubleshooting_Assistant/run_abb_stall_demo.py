"""Interactive development demo. Session state stays in memory until exit."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = 'http://127.0.0.1:8000/development/abb/conditions/stall/clarify'
INDEX = (
    'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
    '_structured_v1_ready_evidence_v1.json'
)


def request_clarification(observations, deferred):
    payload = {
        'index_filename': INDEX,
        'observations': observations,
        'deferred_fact_ids': deferred,
    }
    request = Request(
        URL, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def run_demo(fetch=None, read=None, write=None):
    fetch = request_clarification if fetch is None else fetch
    read = input if read is None else read
    write = print if write is None else write
    observations, deferred = {}, []
    write('ABB Motor stalls - DEVELOPMENT DEMO')
    write('Unreviewed mappings. Use test inputs or existing reports only.')
    write('This does not confirm a fault or approve a repair.')
    write('Use one machine and observation interval throughout this session.')
    write('Answers are kept only in memory; exiting discards this session.\n')

    while True:
        result = fetch(observations, deferred)
        write('\nCurrent report-support results:')
        for item in result['results']:
            write(f"  {item['possible_cause']}: {item['status']}")
        clarification = result['clarification']
        status = clarification['status']
        if status != 'needs_clarification':
            write('\nSession result: ' + status)
            write('No diagnosis confirmed. No repair action approved.')
            return result

        question = clarification['question']
        write('\n' + question['text'])
        write('Source page(s): ' + str(question['page_numbers']))
        write('Evidence: ' + question['evidence_id'])
        write('1 = Reported present')
        write('2 = Reported absent')
        write('3 = Cannot clarify now (defer)')
        write('q = End this session')

        while True:
            choice = read('Your choice: ').strip().lower()
            if choice in ('1', '2', '3', 'q'):
                break
            write('Enter 1, 2, 3, or q.')
        if choice == 'q':
            write('Session ended. No answers saved.')
            return None

        fact = question['fact_id']
        if choice == '3':
            if fact not in deferred:
                deferred.append(fact)
        else:
            # The user supplies the current clarified report for this fact.
            observations[fact] = [choice == '1']
            if fact in deferred:
                deferred.remove(fact)


if __name__ == '__main__':
    try:
        run_demo()
    except HTTPError as error:
        print(f'API error {error.code}: {error.read().decode("utf-8", errors="replace")}')
        raise SystemExit(1)
    except (URLError, TimeoutError) as error:
        print('Could not reach the local API. Start the backend on port 8000.')
        print(str(error))
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nSession ended. No answers saved.')
