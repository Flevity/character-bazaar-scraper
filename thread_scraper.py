from selenium import webdriver
from selenium.webdriver.common.by import By
import sqlite3
import datetime

db_file = 'data.db'
SITE = 'https://forums.eveonline.com/c/marketplace/character-bazaar/'
thread_url = 'https://forums.eveonline.com/t/'
excludes = ['wtb', 'sold', 'new skillboard', 'welcome to the character bazaar', 'private', 'close', 'cancel']
scroll = 1000


def create_connection(file):
    con = None
    try:
        con = sqlite3.connect(file)
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
    cur.close()


def upsert_threads_data(connection, data):
    cur = connection.cursor()
    cur.executemany(f'INSERT INTO threads (id, name, last_update, activity, url) '
                    f'values (:id, :name, :last_update, :activity, :url) '
                    f'on conflict(id) DO UPDATE SET name = excluded.name, last_update = excluded.last_update, '
                    f'activity = excluded.activity, url = excluded.url', data)
    connection.commit()
    print("Threads data pushed to DB.")
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
                'activity': thread.find_element(By.CSS_SELECTOR, '.relative-date').text} for thread in threads
               if all(string not in thread.find_element(By.CSS_SELECTOR, '.title.raw-link.raw-topic-link').text.lower()
                      for string in excludes)]
print(f'{len(thread_data)} thread links parsed.')

for thread in thread_data:
    page.get(thread_url + thread['id'])
    urls = page.find_elements(By.CSS_SELECTOR, '#post_1 .cooked a')
    for url in urls:
        if 'skillboard.eveisesi.space/users/' in url.get_attribute('href'):
            thread['url'] = url.get_attribute('href')

thread_data = [thread for thread in thread_data if 'url' in thread]
print(f'{len(thread_data)} skillboard urls found.')
print(*thread_data, sep='\n')

page.quit()
print('Closing browser.')

conn = create_connection(db_file)
with conn:
    create_schemas(conn)
    upsert_threads_data(conn, thread_data)
