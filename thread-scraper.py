from selenium import webdriver
from selenium.webdriver.common.by import By

SITE = 'https://forums.eveonline.com/c/marketplace/character-bazaar/'
thread_url = 'https://forums.eveonline.com/t/'
excludes = ['wtb', 'sold', 'new skillboard', 'welcome to the character bazaar', 'private']
scroll = 1000

page = webdriver.Chrome()
page.get(SITE)

threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')

while len(threads) < 100:
    page.execute_script(f'window.scrollTo(0, {scroll})')
    scroll += 1000
    threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')
thread_data = [{'id': thread.get_attribute('data-topic-id'),
                'name': thread.find_element(By.CSS_SELECTOR, '.title.raw-link.raw-topic-link').text,
                'activity': thread.find_element(By.CSS_SELECTOR, '.relative-date').text} for thread in threads
               if all(string not in thread.find_element(By.CSS_SELECTOR, '.title.raw-link.raw-topic-link').text.lower()
                      for string in excludes)]

for thread in thread_data:
    page.get(thread_url + thread['id'])
    urls = page.find_elements(By.CSS_SELECTOR, '#post_1 .cooked a')
    for url in urls:
        if 'skillboard.eveisesi.space' in url.get_attribute('href'):
            thread['url'] = url.get_attribute('href')
print(*thread_data, sep='\n')
