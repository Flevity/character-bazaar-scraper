from selenium import webdriver
from selenium.webdriver.common.by import By
import sqlite3

SITE = 'https://forums.eveonline.com/c/marketplace/character-bazaar/'
thread_url = 'https://forums.eveonline.com/t/'
excludes = ['wtb', 'sold', 'new skillboard', 'welcome to the character bazaar', 'private', 'close', 'cancel']
scroll = 1000

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

db_file = 'data.db'
table_name = 'parser_data'

try:
    sqlite_connection = sqlite3.connect(db_file)
    cursor = sqlite_connection.cursor()
    print("DB created and connected.")

    cursor.execute(f'CREATE TABLE if not exists {table_name} (id integer NOT NULL primary key, name text, activity '
                   'text, url text);')

    cursor.executemany(f'insert into {table_name}(id, name, activity, url) values (:id, :name, :activity, :url) on '
                       'conflict(id) DO UPDATE SET name = excluded.name, activity = excluded.activity, '
                       'url = excluded.url', thread_data)

    sqlite_connection.commit()
    print("Data pushed to DB.")
    cursor.close()
except sqlite3.Error as error:
    print("Sqlite error:", error)
finally:
    if sqlite_connection:
        sqlite_connection.close()
        print("SQLite connection closed.")
    page.quit()
    print('Closing browser.')
