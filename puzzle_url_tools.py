import configparser

config = configparser.ConfigParser()
config.read('config.ini')

import re
emojis = re.compile(r'<[^>]+alt="([^"]+)"[^>]+>')

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import io
from PIL import Image

options = Options()
options.add_argument("--headless=new")
options.add_experimental_option("detach", True)

service = Service(config['DEFAULT']['CHROME_PATH'])

driver = webdriver.Chrome(options=options)#, service=service)

def get_image_and_rules(url):
    print(f"Loading {url}")
    driver.get(url)

    # Make sure the page is loaded properly
    WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, 'dialog')))
    WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'svgrenderer')))

    # Hide SvenPeek so it does not appear on the screenshot
    driver.execute_script('document.getElementById("svenpeek").remove()')

    # Acknowledges the dialog
    dialog = driver.find_element(By.CLASS_NAME, 'dialog')
    dialog.find_element(By.CSS_SELECTOR, 'button').click()

    # Screenshot the puzzle image
    image_binary = driver.find_element(By.ID, 'svgrenderer').screenshot_as_png
    img = io.BytesIO(image_binary)

    # Get the rest of the data from the page
    title = driver.find_element(By.CLASS_NAME, 'puzzle-title').text
    author = driver.find_element(By.CLASS_NAME, 'puzzle-author').text[4:] # Remove " by " at the begining of the Author name
    rules = driver.find_element(By.CLASS_NAME, 'puzzle-rules').get_attribute("innerHTML")
    rules = rules.replace("<br>", "")
    rules = emojis.sub(r"\1", rules)
    
    return title, author, rules, img

def puzzle_desc(url):
    title = author = rules = img = None
    try:
        title, author, rules, img = get_image_and_rules(url)
    except Exception as e:
        print(e)
    if title:
        return f"**{title}** by **{author}**\n\n**Rules:**\n{rules}\n\nSudokuPad: {url}", img
    else:
        return f"Link: {url}\n\n_Bot could not retreive more info... sorry_", img

if __name__ == '__main__':
    pass