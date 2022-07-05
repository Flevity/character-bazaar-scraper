from selenium import webdriver
from selenium.webdriver.common.by import By

SITE = 'https://forums.eveonline.com/c/marketplace/character-bazaar/'

page = webdriver.Chrome()
page.get(SITE)
scroll = 1000

threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')

while len(threads) < 100:
    page.execute_script(f'window.scrollTo(0, {scroll})')
    scroll += 1000
    threads = page.find_elements(By.CSS_SELECTOR, '.topic-list-item')
thread_data = [{'id': thread.get_attribute('data-topic-id'),
                'name': thread.find_element(By.CSS_SELECTOR, '.title.raw-link.raw-topic-link').text,
                'activity': thread.find_element(By.CSS_SELECTOR, '.relative-date').text} for thread in threads]

print(*thread_data, sep='\n')
