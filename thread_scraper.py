from selenium import webdriver
from selenium.webdriver.common.by import By
import sqlite3
import datetime
import requests
import json

db_file = 'data.db'
SITE = 'https://forums.eveonline.com/c/marketplace/character-bazaar/'
thread_url = 'https://forums.eveonline.com/t/'
excludes = ['wtb', 'sold', 'new skillboard', 'welcome to the character bazaar', 'private', 'close', 'cancel', 'delete']
scroll = 1000


def create_connection(file):
    con = None
    try:
        con = sqlite3.connect(file)
        con.cursor().execute('PRAGMA foreign_keys = ON')
        con.cursor().close()
        print("DB created and connected.")
    except sqlite3.Error as e:
        print(e)

    return con


def create_schemas(connection):
    cur = connection.cursor()

    cur.execute(f'CREATE TABLE if not exists threads ('
                f'id integer primary key, '
                f'name text, '
                f'last_update timestamp, '
                f'activity text, '
                f'url text);')

    cur.execute(f'CREATE TABLE if not exists skill_groups ('
                f'id integer primary key, '
                f'name text);')

    cur.execute(f'CREATE TABLE if not exists skills ('
                f'id integer primary key, '
                f'name text, '
                f'group_id integer NOT NULL, '
                f'FOREIGN KEY(group_id) REFERENCES skill_groups(id));')

    cur.execute(f'CREATE TABLE if not exists skillboard_urls ('
                f'id integer primary key, '
                f'url text, '
                f'character_id integer, '
                f'last_update timestamp,'
                f'thread_id integer NOT NULL, '
                f'CONSTRAINT thread_id FOREIGN KEY(thread_id) REFERENCES threads(id) '
                f'ON DELETE CASCADE '
                f'CONSTRAINT character_id FOREIGN KEY(character_id) REFERENCES characters(id) '
                f'ON DELETE CASCADE);')

    cur.execute(f'CREATE TABLE if not exists character_skills ('
                f'character_id integer NOT NULL,'
                f'skill_id interger NOT NULL,'
                f'skill_lvl integer,'
                f'UNIQUE(character_id, skill_id),'
                f'FOREIGN KEY(skill_id) REFERENCES skills(id),'
                f'CONSTRAINT character_id FOREIGN KEY(character_id) REFERENCES characters(id));')

    cur.execute(f'CREATE TABLE if not exists characters ('
                f'id integer primary key, '
                f'skills_last_update timestamp NOT NULL);')

    cur.close()


def upsert_threads_data(connection, data):
    cur = connection.cursor()
    cur.executemany(f'INSERT INTO threads (id, name, last_update, activity) '
                    f'values (:id, :name, :last_update, :activity) '
                    f'on conflict(id) DO UPDATE SET name = excluded.name, last_update = excluded.last_update, '
                    f'activity = excluded.activity', data)
    connection.commit()
    print(f"{len(data)} threads pushed to DB.")
    cur.close()


def delete_irrelevant_threads(connection):
    cur = connection.cursor()
    rows = cur.execute('SELECT id, name FROM threads').fetchall()
    irrelevant_thread_ids = tuple([row[0] for row in rows if any(word in row[1].lower() for word in excludes)])
    cur.execute(f'DELETE FROM threads WHERE id in {irrelevant_thread_ids}')
    connection.commit()
    print(f'{len(irrelevant_thread_ids)} irrelevant threads deleted.')
    cur.close()


def parse_skillboard_urls(connection):
    cur = connection.cursor()
    rows = cur.execute('SELECT threads.id FROM threads '
                       'LEFT JOIN skillboard_urls ON threads.id = skillboard_urls.thread_id '
                       'WHERE skillboard_urls.url is NULL').fetchall()
    print(f'Starting to parse urls in {len(rows)} threads')
    urls = [row[0] for row in rows]
    skillboard_urls = []
    for url in urls:
        page.get(thread_url + str(url))
        hrefs = page.find_elements(By.CSS_SELECTOR, '#post_1 .cooked a')
        if hrefs:
            for href in hrefs:
                if 'skillboard.eveisesi.space/users/' in href.get_attribute('href'):
                    skillboard_urls.append((href.get_attribute('href'), url))
                else:
                    skillboard_urls.append((None, url))
        else:
            skillboard_urls.append((None, url))
    unique_skillboard_urls = []
    for url in skillboard_urls:
        if url not in unique_skillboard_urls:
            unique_skillboard_urls.append(url)
    print(f'{len([row for row in unique_skillboard_urls if row[0] is not None])} skillboard ulrs found')
    cur.executemany(f'INSERT INTO skillboard_urls (url, thread_id) '
                    f'values (:0, :1) ', unique_skillboard_urls)
    connection.commit()
    cur.execute(f'DELETE FROM threads WHERE id IN (SELECT threads.id FROM threads LEFT JOIN skillboard_urls '
                f'ON threads.id = skillboard_urls.thread_id WHERE skillboard_urls.url is NULL)')
    connection.commit()
    print(f"Skillboard urls pushed to DB")
    cur.close()

    page.quit()
    print('Closing browser.')


def get_skillboard_json(connection, url):
    start_json = 'JSON.parse(`'
    end_json = 'console.log(skillzGrouped)'
    r = requests.get(url)
    body = r.text
    skills = body[body.find(start_json) + len(start_json):body.find(end_json)].strip()[:-2]
    try:
        data = json.loads(skills)
        return data
    except json.decoder.JSONDecodeError as error:
        print(f'There was a problem with JSON decoding, probably the broken url was used. {error}, url: {url}')
        cur = connection.cursor()
        cur.execute(f"DELETE FROM skillboard_urls WHERE url = '{url}';")
        connection.commit()
        cur.close()
        return None


def parse_skills(connection, data):
    categories, skills = [], []
    cur = connection.cursor()
    for category in data:
        categories.append((category["id"], category["name"]))
        for skill in category["items"]:
            skills.append((skill["id"], skill["name"], skill["group_id"]))
    cur.executemany(f'INSERT INTO skill_groups(id, name) '
                    f'values (:id, :name) '
                    f'on conflict(id) DO UPDATE SET name = excluded.name', categories)

    cur.executemany(f'INSERT INTO skills(id, name, group_id) '
                    f'values (:id, :name, :group_id) '
                    f'on conflict(id) DO UPDATE SET name = excluded.name, group_id = excluded.group_id;', skills)
    connection.commit()
    cur.close()


def parse_character_skills(connection, data, url_id):
    cur = connection.cursor()
    character_skills = []
    for category in data:
        for skill in category["skills"]:
            if skill["skill"]:
                character_skills.append((skill["id"], skill["skill"]["trained_skill_level"],
                                         skill["skill"]["character_id"]))

    cur.execute(f'INSERT INTO characters(id, skills_last_update) '
                f'VALUES ({character_skills[0][2]}, "{datetime.datetime.now()}") '
                f'on conflict(id) DO UPDATE SET skills_last_update = excluded.skills_last_update;')

    cur.execute(f'UPDATE skillboard_urls '
                f'SET character_id = {character_skills[0][2]} '
                f'WHERE id = {url_id};')

    cur.executemany('INSERT INTO character_skills(skill_id, skill_lvl, character_id) '
                    'VALUES (:skill_id, :skill_lvl, :character_id)'
                    'on conflict(character_id, skill_id) '
                    'DO UPDATE SET skill_lvl = excluded.skill_lvl;', character_skills)
    connection.commit()
    cur.close()


firefox_options = webdriver.FirefoxOptions()
page = webdriver.Remote(
    command_executor='127.0.0.1:4444',
    options=firefox_options
)
page.get(SITE)

threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')

while len(threads) < 200:
    page.execute_script(f'window.scrollTo(0, {scroll})')
    scroll += 1000
    threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')
thread_data = [{'id': thread.get_attribute('data-topic-id'),
                'name': thread.find_element(By.CSS_SELECTOR, '.title.raw-link.raw-topic-link').text,
                'last_update': datetime.datetime.now(),
                'activity': thread.find_element(By.CSS_SELECTOR, '.relative-date').text} for thread in threads]
print(f'{len(thread_data)} thread links parsed.')

with create_connection(db_file) as conn:
    create_schemas(conn)
    upsert_threads_data(conn, thread_data)
    delete_irrelevant_threads(conn)
    parse_skillboard_urls(conn)

    skillboard_urls = conn.cursor().execute('SELECT url, id FROM skillboard_urls').fetchall()
    conn.cursor().close()

    for skillboard_url in skillboard_urls:
        character_data = get_skillboard_json(conn, skillboard_url[0])
        if character_data:
            parse_skills(conn, character_data)
            parse_character_skills(conn, character_data, skillboard_url[1])
