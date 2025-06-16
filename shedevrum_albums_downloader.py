# данный скрипт парсит альбомы с сайта shedevrum.ai
import sys, os, json, random

from playwright.sync_api import (sync_playwright, expect, Page)

class ShedevrumParser:

    def __init__(self, output_folder:str = '.\\prompt') -> None:
        self.urls_cache:dict[str, bool] = {}

        self.output_folder:str = os.path.abspath(output_folder)
        cache_file_name:str = f'urls_cache_{os.path.basename(self.output_folder)}.json'
        self.urls_cache_path:str = os.path.join(self.output_folder, cache_file_name)

        if not os.path.isdir(self.output_folder):
            os.makedirs(self.output_folder)

        self.browser_args:list = [
            "--start-maximized", 
            '--disable-blink-features=AutomationControlled'
        ]

        self.page_found_els:dict = {
            'next_button': 'Ещё',
            'end_element': "Конец! 🤷‍",

        }

        self.selectors:dict = {
            'post_link': 'a[href^="/post/"]',
            'image': 'article.bg-white img',
            'prompt_block': '.bg-gray-100:has(.prompt), .bg-gray-100:has(.stretch-tabs)',
            'prompt_el': 'span.prompt, .truncate',
            'author_el': 'a[href^="/profile/"], a[href^="/@"]',
            'version_el': 'span.stretch-tabs.whitespace-nowrap',
        }

        self.shedevrum_link = 'https://shedevrum.ai'

    def save_urls_cache(self) -> None:
        """ Save urls cache to json-file """
        with open(self.urls_cache_path, 'w', encoding='utf-8') as fp:
            json.dump(self.urls_cache, fp, indent=4)

    def load_urls_cache(self) -> None:
        """ Try load urls cache from json-file. """
        if not os.path.isfile(self.urls_cache_path): return None

        with open(self.urls_cache_path, 'r', encoding='utf-8') as fp:
            self.urls_cache = json.load(fp)

    def extract_from_page(self, page:Page, url:str) -> bool:
        """ Get picture and prompt from single page. """
        try:
            rndstr = url[:-1].split('/')[-1] if url.endswith('/') else url.split('/')[-1]  
            image_path = os.path.join(self.output_folder, f'{rndstr}.jpg')
            prompt_path = os.path.join(self.output_folder, f'{rndstr}.md')

            page.goto(url)
            
            # Ожидание и получение изображения
            try:
                image = page.locator(self.selectors['image']).first
                expect(image).to_be_visible(timeout=15000)
                src = image.get_attribute('src')
                if not src:
                    raise Exception("Не удалось получить URL изображения")
                    
                resp = page.request.get(src)
                if resp.status != 200:
                    raise Exception(f"Ошибка при скачивании изображения: {resp.status}")
                    
                with open(image_path, 'wb') as f:
                    f.write(resp.body())
            except Exception as e:
                print(f"Ошибка при обработке изображения: {e}")
                return False

            # Ожидание и получение промпта
            try:
                prompt_block = page.locator(self.selectors['prompt_block']).first
                expect(prompt_block).to_be_visible(timeout=15000)
                
                prompt_el = prompt_block.locator(self.selectors['prompt_el']).first
                expect(prompt_el).to_be_visible(timeout=15000)
                prompt_text = prompt_el.inner_text()

                author_el = prompt_block.locator(self.selectors['author_el'])
                if author_el.count():
                    author_link = author_el.last
                    expect(author_link).to_be_visible(timeout=15000)
                    author_name = author_link.inner_text()
                    author_href = self.shedevrum_link + author_link.get_attribute('href')
                else:
                    author_name = ''
                    author_href = ''

                version_el = prompt_block.locator(self.selectors['version_el'])
                if version_el.count():
                    version = version_el.last
                    expect(version).to_be_visible(timeout=15000)
                    version_text = version.inner_text()
                else:
                    version_text = ''

                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(f'{author_name}\n{author_href}\n{prompt_text}\n\n{version_text}')
            except Exception as e:
                print(f"Ошибка при обработке промпта: {e}")
                return False

            self.urls_cache[url] = True
            self.save_urls_cache()
            return True
            
        except Exception as e:
            print(f"Общая ошибка при обработке страницы {url}: {e}")
            return False

    def pics_on_pages(self, urls:list[str]) -> None:
        """
            Get pictures and prompts from the pages.
        """
        with sync_playwright() as p:
            # инициализация браузера (без видимого открытия браузера)
            # browser = p.chromium.launch()
            # инициализация браузера (с явным открытием браузера)
            browser = p.chromium.launch(headless=False, args = self.browser_args)
            # инициализация страницы
            page = browser.new_page()

            for url in urls:
                print(url)
                self.extract_from_page(page, url)

            browser.close()

    def get_bookmarks(self, album_url:str) -> list[str]:
        """
            Open and rolldown the page with posts-links.
            Return list of urls.
        """
        urls = set()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=self.browser_args)
                page = browser.new_page()

                try:
                    page.goto(album_url)
                    
                    next_button = page.get_by_role('button', name=self.page_found_els['next_button'])
                    expect(next_button).to_be_visible(timeout=10000)
                    next_button.click()
                    
                    while True:
                        try:
                            end_element = page.get_by_text(self.page_found_els['end_element'])
                            if end_element.count() > 0:
                                end_element.scroll_into_view_if_needed()
                                break

                            page.mouse.wheel(0, 1000)
                        except TimeoutError:
                            print("Таймаут при прокрутке страницы")
                            break

                    posts_links = page.locator(self.selectors['post_link']).all()
                    for link in posts_links:
                        l = link.get_attribute('href')
                        if l.endswith('#comments'):
                            l = l[:-9]
                        urls.add(self.shedevrum_link + l)
                except Exception as e:
                    print(f"Ошибка при обработке страницы: {e}")
                finally:
                    browser.close()
        except Exception as e:
            print(f"Ошибка при инициализации браузера: {e}")
            
        return list(urls)

    def download_album(self, album_url:str) -> None:
        """
            Download album of images.
        """
        try:

            urls = [] # list of urls for downloading
            self.load_urls_cache()
            if self.urls_cache:
                for key in self.urls_cache:
                    if not self.urls_cache[key]:
                        urls.append(key)
            else:
                urls = self.get_bookmarks(album_url)
                for url in urls:
                    self.urls_cache[url] = False
                self.save_urls_cache()

            if not urls:
                print('Альбом уже закачан. Удалите post_urls.json, чтобы скачать альбом заново.')
                return None
                
            self.pics_on_pages(urls)
        except Exception as e:
            print(f"Ошибка при скачивании альбома: {e}")

def download_album_example():
    # change this paths for correct downloading:
    album_url = 'https://shedevrum.ai/@aleksversus/albums/wp/'
    output_folder = '.\\prompts\\wp'
    # new parser object.
    parser = ShedevrumParser(output_folder)
    # run download album
    parser.download_album(album_url)

def download_list_of_images_example():
    # list of pages (single image on page)
    urls = [
        'https://shedevrum.ai/post/aba1213a1dec11f0abd12aa11dc6dfe1/',
        'https://shedevrum.ai/post/aba064952ee011f0bf11aa21ebb699bc/',
        'https://shedevrum.ai/post/ae1dbfb32e2011f0bf11aa21ebb699bc/',
        'https://shedevrum.ai/post/712c5d432e2011f09eafba31a74c2f35/',
        'https://shedevrum.ai/post/a97d5cd32e1f11f0a6457e3b74b724b2/',
        'https://shedevrum.ai/post/b38b96fd2e1e11f082e616609d737eaa/'
    ]
    # output for saving.
    output_folder = '.\\prompts\\something'
    # new parser object.
    parser = ShedevrumParser(output_folder)
    # download pics
    parser.pics_on_pages(urls)

if __name__ == "__main__":
    download_album_example()    
