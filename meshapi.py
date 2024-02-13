import requests
from datetime import datetime
from pytz import timezone
from dateutil.relativedelta import relativedelta
import aiohttp
import asyncio
import json
import os

db = {}


def load_db() -> None:
    global db

    with open('db.json', 'r', encoding='utf-8') as f:
        db = json.load(f)

    if not os.path.exists("logs"):
        os.mkdir("logs")

    if os.path.exists('logs/log.txt'):
        (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat('logs/log.txt')
        creation_date = datetime.fromtimestamp(mtime).strftime('%d_%m_%Y__%H_%M_%S')
        new_name = f"logs/log_{creation_date}.txt"
        os.rename('logs/log.txt', new_name)

    open('logs/log.txt', 'w').close()


def save_db() -> None:
    global db

    with open('db.json', 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)


def date_to_msk(date) -> datetime:
    return timezone("Etc/UTC").localize(date).astimezone(timezone('Europe/Moscow'))


async def get(url, session: aiohttp.ClientSession, headers, cookies):
    try:
        async with session.get(url=url, headers=headers, cookies=cookies) as response:
            resp = await response.text()
            return resp, response.status
    except Exception as e:
        print("Unable to get url {} due to {}.".format(url, e.__class__))


async def async_request(urls, headers={}, cookies={}):
    async with aiohttp.ClientSession() as session:
        result = await asyncio.gather(*[get(url, session, headers, cookies) for url in urls])
        res_code = 200
        for _, code in result:
            if code != 200:
                res_code = code
        return [x[0] for x in result], res_code


async def profile(chat_id):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        data = requests.get("https://school.mos.ru/api/family/mobile/v1/profile", headers={
            'auth-token': token,
            'profile-id': student_id,
            'x-mes-subsystem': 'familymp'
        })
        if data.status_code != 200:
            return None
        return data.text
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "profile" for chat_id {chat_id} ({str(e)})')
        return None


async def schedule(chat_id, date1: datetime, date2: datetime):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        urls = []

        date = date1
        while True:
            urls.append(f"https://school.mos.ru/api/family/mobile/v1/schedule/?student_id={student_id}&date={date.strftime('%Y-%m-%d')}")

            date += relativedelta(days=1)
            if date > date2:
                break

        res, code = await async_request(urls, {
            "x-mes-subsystem": "familymp",
            "auth-token": token
        })

        if code != 200:
            return None
        
        return res
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "schedule" for chat_id {chat_id} ({str(e)})')
        return None


async def homework(chat_id, date1: datetime, date2: datetime):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        data = requests.get(f'https://dnevnik.mos.ru/core/api/student_homeworks?begin_prepared_date={date1.strftime("%d.%m.%Y")}&end_prepared_date={date2.strftime("%d.%m.%Y")}&student_profile_id={student_id}', headers={
            "Auth-token": token,
            "Profile-Id": student_id
        }, cookies={
            "auth_token": token,
            "student_id": student_id
        })

        if data.status_code != 200:
            return None

        res = {}

        test_urls = []
        execute_tests = ['TestSpecBinding', 'Workbook', 'FizikonModule']

        for entry in data.json():
            obj = {}
            date = entry['homework_entry']['homework']['date_prepared_for']
            obj['created_at'] = date_to_msk(datetime.strptime(entry['created_at'], '%d.%m.%Y %H:%M')).strftime("%d.%m.%Y %H:%M")
            obj['updated_at'] = date_to_msk(datetime.strptime(entry['updated_at'], '%d.%m.%Y %H:%M')).strftime("%d.%m.%Y %H:%M")
            obj['text'] = entry['homework_entry']['description']
            obj['subject'] = entry['homework_entry']['homework']['subject']['name']

            obj['attachements'] = []
            for att in entry['homework_entry']['attachments']:
                obj['attachements'].append({
                    'name': att['file_file_name'],
                    'url': ('https://dnevnik.mos.ru' + att['path']).replace(' ', '%20')
                })

            tests = json.loads(entry['homework_entry']['data'])['materialObj']

            obj['tests'] = {
                'execute': [],
                'examine': len([x for x in tests if x['type'] not in execute_tests])
            }

            for test in tests:
                if test['type'] in execute_tests:
                    obj['tests']['execute'].append({
                        'name': test['name'],
                        'url': len(test_urls)
                    })
                    test_urls.append(
                        f'https://school.mos.ru/api/ej/partners/v1/homeworks/launch?homework_entry_id={entry["homework_entry"]["id"]}&material_id={test["uuid"]}')

            if date not in res:
                res[date] = []
            res[date].append(obj)

        test_urls2, code = await async_request(test_urls, headers={
            'Auth-Token': token,
            'Profile-Id': student_id,
            'X-Mes-Subsystem': 'familyweb'
        })

        if code != 200 and code != 302:
            return None

        for date, entries in res.items():
            for entry in entries:
                for test in entry['tests']['execute']:
                    test['url'] = test_urls2[test['url']]

        res = sorted(res.items(), key=lambda x: (datetime.strptime(x[0], '%d.%m.%Y')))

        return res
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "homework" for chat_id {chat_id} ({str(e)})')
        return None


async def marksdate(chat_id, date1: datetime, date2: datetime):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        data = requests.get(f"https://dnevnik.mos.ru/core/api/marks?created_at_from={date1.strftime('%d.%m.%Y')}&created_at_to={date2.strftime('%d.%m.%Y')}&student_profile_id={student_id}", headers={
            "Auth-token": token,
            "Profile-Id": student_id
        }, cookies={
            'auth_token': token,
            'student_id': student_id
        })

        if data.status_code != 200:
            return None

        res = {}

        for entry in data.json():
            date = entry['date']
            if not date in res:
                res[date] = {}

            subject_id = str(entry['subject_id'])
            if not subject_id in res[date]:
                res[date][subject_id] = []

            res[date][subject_id].append({
                'value': int(entry['name']),
                'weight': int(entry['weight']),
                'comment': entry['comment'],
                # 'created_at': date_to_msk(datetime.strptime(entry['created_at'], '%d.%m.%Y %H:%M')).strftime('%d.%m.%Y %H:%M'),
                # 'updated_at': date_to_msk(datetime.strptime(entry['updated_at'], '%d.%m.%Y %H:%M')).strftime('%d.%m.%Y %H:%M'),
                'is_exam': entry['is_exam']
            })

        subj_url = f'https://dnevnik.mos.ru/core/api/subjects?ids={",".join([str(element) for day in res.values() for element in day])}'
        data2 = requests.get(subj_url, headers={
            'Auth-token': token,
            'Profile-Id': student_id
        }, cookies={
            'auth_token': token,
            'student_id': student_id
        })

        if data2.status_code != 200:
            return None

        subjects = {}
        for entry in data2.json():
            subjects[str(entry['id'])] = entry['name']

        for day in res.values():
            for subj in list(day.keys()):
                day[subjects[subj]] = day.pop(subj)

        res = sorted(res.items(), key=lambda x: datetime.strptime(x[0], '%d.%m.%Y'))

        return res
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "marksdate" for chat_id {chat_id} ({str(e)})')
        return None


async def marks(chat_id):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        years = requests.get("https://dnevnik.mos.ru/core/api/academic_years")
        this_year = [year['id'] for year in years.json() if year['current_year'] == True][0]

        data = requests.get(f'https://dnevnik.mos.ru/reports/api/progress/json?academic_year_id={this_year}&student_profile_id={student_id}', headers={
            'Auth-Token': token,
            'Profile-Id': student_id
        }, cookies={
            'auth_token': token,
            'student_id': student_id
        })

        if data.status_code != 200:
            return None

        res = {}

        for entry in data.json():
            obj = {}
            res[entry['subject_name']] = obj

            obj['avg'] = entry['avg_five']

            obj['periods'] = {}
            for period in entry['periods']:
                obj2 = {}
                obj['periods'][period['name']] = obj2

                obj2['marks'] = []
                for mark in period['marks']:
                    obj2['marks'].append({
                        'value': int(mark['values'][0]['original']),
                        'weight': mark['weight'],
                        'is_exam': mark['is_exam']
                    })

                obj2['avg'] = period['avg_five']
                obj2['final_mark'] = period['final_mark'] if 'final_mark' in period else None

        # print(res)

        return res
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "marks" for chat_id {chat_id} ({str(e)})')
        return None


async def notifications(chat_id):
    global db
    if not chat_id in db:
        return None

    token = db[chat_id]['token']
    student_id = db[chat_id]['student_id']

    try:
        data = requests.get(f"https://school.mos.ru/api/family/mobile/v1/notifications/search?student_id={student_id}", headers={
            'Auth-Token': token,
            'Profile-Id': student_id,
            "x-mes-subsystem": "familymp"
        })

        if data.status_code != 200:
            return None

        return data.json()
    except Exception as e:
        with open('logs/log.txt', 'a') as f:
            f.write(f'{datetime.now().strftime("[%d.%m.%Y %H:%M:%S]")} Error: "notifications" for chat_id {chat_id} ({str(e)})')
        return None


async def try_add_new_token(token, chat_id) -> bool:
    global db

    # get profile id
    req = requests.post("https://dnevnik.mos.ru/lms/api/sessions", json={
        'auth_token': token
    }, headers={
        'Auth-Token': token
    }, cookies={
        'auth_token': token
    })

    if req.status_code != 200:
        print('Failed to get token info!')
        return False

    data = req.json()

    student_id = str(data["profiles"][0]["id"])

    print(f'Token: {token[:100]}... Student id: {student_id} Name: {data["last_name"]} {data["first_name"]} {data["middle_name"]}')

    db[str(chat_id)] = {
        'token': token,
        'student_id': student_id
    }

    save_db()

    return True
