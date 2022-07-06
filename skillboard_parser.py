import requests
import json


def get_skillboard_json(url):
    start_json = 'JSON.parse(`'
    end_json = 'console.log(skillzGrouped)'
    r = requests.get(url)
    body = r.text
    skills = body[body.find(start_json) + len(start_json):body.find(end_json)].strip()[:-2]
    try:
        return json.loads(skills)
    except json.decoder.JSONDecodeError as error:
        print('There was a problem with JSON decoding, probably the broken url was used.', error)
        return -1


json_data = get_skillboard_json('https://skillboard.eveisesi.space/users/f4b302f008ce08ec7a7220674477617f23f9dcb0/')
for category in json_data:
    print(category["name"])
    for skill in category["skills"]:
        if skill["skill"]:
            print(skill["name"], skill["skill"]["trained_skill_level"])
        else:
            continue
    print()
