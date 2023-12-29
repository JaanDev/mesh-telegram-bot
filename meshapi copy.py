import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import aiohttp
import asyncio
import json
import urllib.parse


async def get(url, session: aiohttp.ClientSession, headers, cookies):
    try:
        # print(f'url={url};headers={headers};cookies={cookies}')
        async with session.get(url=url, headers=headers, cookies=cookies) as response:
            resp = await response.text()
            return resp
    except Exception as e:
        print("Unable to get url {} due to {}.".format(url, e.__class__))


async def async_request(urls, headers={}, cookies={}):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(*[get(url, session, headers, cookies) for url in urls])


def profile(token, student_id):
    data = requests.get("https://school.mos.ru/api/family/mobile/v1/profile", headers={
        'auth-token': token,
        'profile-id': str(student_id),
        'x-mes-subsystem': 'familymp'
    })
    return data.text


async def schedule(token, student_id, date1: datetime, date2: datetime):
    urls = []

    date = date1
    while True:
        urls.append(f"https://school.mos.ru/api/family/mobile/v1/schedule/?student_id={student_id}&date={date.strftime('%Y-%m-%d')}")

        date += relativedelta(days=1)
        if date > date2:
            break

    return await async_request(urls, {
        "x-mes-subsystem": "familymp",
        "auth-token": token
    })


async def homework(token, student_id, date1: datetime, date2: datetime):
    data = requests.get(f'https://dnevnik.mos.ru/core/api/student_homeworks?begin_prepared_date={date1.strftime("%d.%m.%Y")}&end_prepared_date={date2.strftime("%d.%m.%Y")}&student_profile_id={student_id}', headers={
        "Auth-token": token,
        "Profile-Id": str(student_id)
    }, cookies={
        "auth_token": token,
        "student_id": str(student_id)
    })

    res = {}

    for entry in data.json():
        obj = {}
        date = entry['homework_entry']['homework']['date_prepared_for']
        obj['created_at'] = entry['created_at']
        obj['updated_at'] = entry['updated_at']
        obj['text'] = entry['homework_entry']['description']
        obj['subject'] = entry['homework_entry']['homework']['subject']['name']

        obj['attachements'] = []
        for att in entry['homework_entry']['attachments']:
            obj['attachements'].append({
                'name': att['file_file_name'],
                'url': ('https://dnevnik.mos.ru/' + att['path']).replace(' ', '%20')
            })

        obj['tests'] = {
            'execute': [],
            'examine': []
        }

        tests = json.loads(entry['homework_entry']['data'])

        if 'materialObj' in tests:
            urls = [
                f'https://school.mos.ru/api/ej/partners/v1/homeworks/launch?homework_entry_id={entry["homework_entry"]["id"]}&material_id={x["uuid"]}' for x in tests['materialObj']]
            urls2 = await async_request(urls, headers={
                'Auth-Token': token,
                'Profile-Id': str(student_id),
                'X-Mes-Subsystem': 'familyweb'
            })

            for i, n in enumerate(tests['materialObj']):
                if n['type'] in ['TestSpecBinding', 'Workbook', 'FizikonModule']:
                    obj['tests']['execute'].append({
                        'name': n['name'],
                        'url': urls2[i]
                    })
                else:
                    obj['tests']['examine'].append({
                        'name': n['name'],
                        'url': urls2[i]
                    })

        if date not in res:
            res[date] = []
        res[date].append(obj)

    with open('amogus.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=4, ensure_ascii=False)

    return res
