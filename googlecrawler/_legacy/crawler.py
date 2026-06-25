from newspaper import Article, Config, ArticleException

def download_and_parse_article(url_list):
    """
    Downloads and parses an article from a list of URLs, catching HTTP errors >= 400.
    """
    config = Config()
    config.request_timeout = 10  # Set a timeout (in seconds)

    article_contents = []  # Initialize an empty list to store article contents

    for url in url_list:
        try:
            article = Article(url, config=config)
            article.download()
            article.parse()
            article_contents.append(article.text.replace("\n\n", "")) # append the text to the list.
        except ArticleException as e:
            if "HTTP Error 4" in str(e) or "HTTP Error 5" in str(e): #check the message for http errors.
                print(f"HTTP Error for URL: {url}: {e}")
            else:
                print(f"ArticleException for URL: {url}: {e}")
            article_contents.append("") # append empty string on error.
        except Exception as e:
            print(f"An unexpected error occurred for URL {url}: {e}")
            article_contents.append("") # append empty string on error.
    return article_contents # return the finished list of article contents.
# ==============
if __name__ == "__main__":

    google_news_url = [
        'https://www.home.saxo/content/articles/equities/rheinmetall-the-nvidia-of-defence-21032025',
        'https://seekingalpha.com/article/4764838-rheinmetall-why-the-european-defense-stalwart-stock-remains-a-buy',
        'https://www.ft.com/content/f4bb94b3-afba-4661-812b-bbba26d0f7ec',
        'https://www.rheinmetall.com/en/media/news-watch/news/2024/12/2024-12-19-rheinmetall-wins-d-lbo-contract-for-vehicle-integration',
        'https://www.reuters.com/business/aerospace-defense/rheinmetall-ceo-sees-faster-growth-pressure-europe-boost-its-defences-mounts-2025-02-14/'
    ]

    articles = download_and_parse_article(google_news_url)
    print(articles)