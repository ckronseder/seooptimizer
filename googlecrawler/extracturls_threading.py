import requests
import threading
import time
import re

def download_google_news_threaded(urls):
    """
    Downloads content from a list of URLs concurrently using threading
    and returns a dictionary with URL as key and content/error as value.

    Args:
        urls (list): A list of URLs (strings) to download.

    Returns:
        dict: A dictionary where keys are the URLs and values are either
              the downloaded content (string) or an error message (string).
    """
    # Dictionary to store the results (URL: content or error)
    downloaded_articles = {}

    # Lock to protect the dictionary from concurrent writes
    dictionary_lock = threading.Lock()

    def _download_single_url(url, articles_dict, lock):
        """Helper function to download a single URL and store it safely."""
        content = None
        error_message = None
        try:
            # print(f"Starting download for: {url}") # Optional: print inside thread
            response = requests.get(url, timeout=10) # Added a timeout
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            content = response.text
            # print(f"Finished download for: {url} (Status: {response.status_code})") # Optional: print inside thread
        except requests.exceptions.Timeout:
            error_message = f"Timeout occurred for {url}"
            # print(error_message) # Optional: print inside thread
        except requests.exceptions.RequestException as e:
            error_message = f"Error downloading {url}: {e}"
            # print(error_message) # Optional: print inside thread
        except Exception as e:
            error_message = f"An unexpected error occurred for {url}: {e}"
            # print(error_message) # Optional: print inside thread

        # Acquire the lock before writing to the shared dictionary
        with lock:
            if content is not None:
                articles_dict[url] = content
            else:
                articles_dict[url] = f"Error: {error_message}" # Store the error message

    # List to hold thread objects
    threads = []

    # Create and start a thread for each URL
    print(f"Starting threaded download of {len(urls)} URLs...")
    for url in urls:
        # Pass the shared dictionary and the lock to the target function
        thread = threading.Thread(target=_download_single_url, args=(url, downloaded_articles, dictionary_lock))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All threads finished.")
    return downloaded_articles

def extract_urls(news_feed):

    urls = []
    for key in news_feed:
        contents = news_feed[key].split(r",")
        url_pattern = r"https://(?!.*(?:jpg|webp|JPG|png|svg|favicon|FAVICON|google|gstatic|schema|thumbnail|image|chart|yimg))[^\s]+"  # Removes certain fixed URLs
        for content in contents:
            url = re.findall(url_pattern, content)
            if url:
                modified_url = url[0].encode('utf-8').decode(
                    'unicode_escape')  # the split text is a collection of lists. Each list can contain one single URL, which is here extracted
                url = re.sub(r'\\.*?\\', '', modified_url)  # Remove certain characters
                url = re.sub(r'"]]"|"]"|"|]]|]', '', url)  # Remove residuals from the string extraction
                # print(url)
                urls.append(url)
        # print(urls)
        urls = list(set(url for url in urls))  # remove duplicates

    return urls


# --- Main part of the script ---

if __name__ == "__main__":
    # A list of sample URLs (replace with actual news article URLs)
    sample_urls = [
        "https://news.google.com/search?tbm=nws&q=Alphabet+&hl=US&gl=US&tbs=qdr:w",
        "https://news.google.com/search?tbm=nws&q=GOOG.US&hl=US&gl=US&tbs=qdr:w"
        "https://news.google.com/search?tbm=nws&q=artificial+intelligence&hl=en&gl=US&tbs=qdr:w",
        "https://news.google.com/search?tbm=nws&q=climate+change&hl=fr&gl=FR&tbs=qdr:m",
        "https://news.google.com/search?tbm=nws&q=stocks&hl=de&gl=DE&tbs=qdr:d"
    ]
    single_url = [
        "https://news.google.com/search?tbm=nws&q=Alphabet+&hl=US&gl=US&tbs=qdr:w",
    ]


    start_time = time.time()

    # Call the function to perform the threaded download
    download_results = download_google_news_threaded(sample_urls)

    end_time = time.time()



    print(f"\nTotal time taken: {end_time - start_time:.2f} seconds")

    # Process the results from the returned dictionary
    print("\n--- Download Results Summary ---")
    success_count = 0
    error_count = 0
    for url, result in download_results.items():
        if isinstance(result, str) and result.startswith("Error:"):
            print(f"URL: {url} - {result}")
            error_count += 1
        else:
            print(f"URL: {url} - Success, content length {len(result)}") # Optional: print success
            success_count += 1

    print(f"\nSuccessfully downloaded: {success_count} articles")
    print(f"Failed to download: {error_count} articles")

    print(len(extract_urls(download_results)))
    print(extract_urls(download_results))

