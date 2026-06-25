import newspaper
import threading
import time
from newspaper import Article

def download_and_parse_article(urls):
    """
    Downloads and parses news articles from a list of URLs concurrently
    using the newspaper library and threading.

    Args:
        urls (list): A list of URLs (strings) to download and parse.

    Returns:
        dict: A dictionary where keys are the URLs and values are either
              a dictionary containing parsed article attributes (like title,
              text, authors, publish_date) or an error message string.
    """
    # Dictionary to store the results (URL: parsed_data or error)
    downloaded_articles_data = {}

    # Lock to protect the dictionary from concurrent writes
    dictionary_lock = threading.Lock()

    def _download_and_parse_article(url, articles_dict, lock):
        """
        Helper function to download, parse a single URL using newspaper,
        and store the result safely.
        """
        article_data = None
        error_message = None
        try:
            print(f"Starting processing for: {url}")
            article = Article(url)
            article.download() # Download the HTML
            article.parse()    # Parse the article content
            # article.nlp()    # Optional: Run NLP for keywords, summary etc.

            # Store relevant parsed data
            article_data = {
                "title": article.title,
                "text": article.text,
                "authors": article.authors,
                "publish_date": article.publish_date,
                "top_image": article.top_image,
                "movies": article.movies,
                "url": article.url # Store the original URL
                # Add other attributes you might need
            }
            print(f"Finished processing for: {url} (Title: {article.title[:50]}...)")

        # Corrected the exception type here
        except newspaper.ArticleException as e:
            error_message = f"Newspaper Article Error for {url}: {e}"
            print(error_message)
        except requests.exceptions.RequestException as e:
             error_message = f"Requests Error downloading {url}: {e}"
             print(error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred for {url}: {e}"
            print(error_message)

        # Acquire the lock before writing to the shared dictionary
        with lock:
            if article_data is not None:
                articles_dict[url] = article_data
            else:
                articles_dict[url] = f"Error: {error_message}" # Store the error message

    # List to hold thread objects
    threads = []

    # Create and start a thread for each URL
    print(f"Starting threaded download and parsing of {len(urls)} URLs with newspaper...")
    for url in urls:
        # Pass the shared dictionary and the lock to the target function
        thread = threading.Thread(target=_download_and_parse_article, args=(url, downloaded_articles_data, dictionary_lock))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All newspaper threads finished.")
    return downloaded_articles_data

# --- Main part of the script ---

if __name__ == "__main__":
    # A list of sample news article URLs (replace with actual URLs)
    sample_news_urls = [
        'https://www.home.saxo/content/articles/equities/rheinmetall-the-nvidia-of-defence-21032025',
        'https://seekingalpha.com/article/4764838-rheinmetall-why-the-european-defense-stalwart-stock-remains-a-buy',
        'https://www.ft.com/content/f4bb94b3-afba-4661-812b-bbba26d0f7ec',
        'https://www.rheinmetall.com/en/media/news-watch/news/2024/12/2024-12-19-rheinmetall-wins-d-lbo-contract-for-vehicle-integration',
        'https://www.reuters.com/business/aerospace-defense/rheinmetall-ceo-sees-faster-growth-pressure-europe-boost-its-defences-mounts-2025-02-14/'
    ]
    single_url = [
        'https://www.reuters.com/business/aerospace-defense/rheinmetall-ceo-sees-faster-growth-pressure-europe-boost-its-defences-mounts-2025-02-14/'
    ]

    start_time = time.time()

    # Call the function to perform the threaded download and parsing
    news_article_results = download_and_parse_article(sample_news_urls)

    end_time = time.time()

    print(f"\nTotal time taken: {end_time - start_time:.2f} seconds")

    # Process the results from the returned dictionary
    print("\n--- Newspaper Download and Parsing Results Summary ---")
    success_count = 0
    error_count = 0
    for url, result in news_article_results.items():
        print(f"\nURL: {url}")
        if isinstance(result, str) and result.startswith("Error:"):
            print(f"Result: {result}")
            error_count += 1
        else:
            print(f"Result: Successfully parsed.")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Authors: {', '.join(result.get('authors', ['N/A']))}")
            print(f"  Publish Date: {result.get('publish_date', 'N/A')}")
            print(f"  Text Length: {len(result.get('text', ''))} characters")
            # print(f"  Text Snippet: {result.get('text', '')[:200]}...") # Uncomment to see text snippet
            success_count += 1

    print(f"\nSuccessfully processed: {success_count} articles")
    print(f"Failed to process: {error_count} articles")

    # Example of accessing data for a specific URL
    # some_news_url = "https://www.bbc.com/news/world-us-canada-67892201"
    # if some_news_url in news_article_results and not isinstance(news_article_results[some_news_url], str):
    #     article_data = news_article_results[some_news_url]
    #     print(f"\nAccessing data for {some_news_url}:")
    #     print(f"  Title: {article_data.get('title')}")
    #     print(f"  First 100 chars of text: {article_data.get('text', '')[:100]}...")
