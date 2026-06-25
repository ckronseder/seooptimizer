import requests
import re
#============

def download_google_news_urls(url_list):
    """
    Function to create a list of clean URLs from Google website
    :param url_list: list of urls
    :return: list of urls with news belonging to search item in the url
    """
    news_urls = []
    items_clean_list = []
    for url in url_list:
        print(url)
        result = requests.get(url)
        items = find_https_urls(result.text)
        items_clean_list.append(items)
    news_urls = items_clean_list
    return [item for sublist in news_urls for item in sublist]


def find_https_urls(text):
    """
    Identifies URLs starting with "https://" in any given text.
    :param text: The input string to search for URLs.
    :return: A list of URLs found in the text.
    """
    urls = []
    contents = text.split(r",")
    url_pattern = r"https://(?!.*(?:jpg|webp|JPG|png|svg|favicon|FAVICON|google|gstatic|schema|thumbnail|image|chart|yimg))[^\s]+" #Removes certain fixed URLs
    for content in contents:
        url = re.findall(url_pattern, content)
        if url:
            modified_url = url[0].encode('utf-8').decode('unicode_escape') #the split text is a collection of lists. Each list can contain one single URL, which is here extracted
            url = re.sub(r'\\.*?\\', '', modified_url) #Remove certain characters
            url = re.sub(r'"]]"|"]"|"|]]|]', '', url) # Remove residuals from the stringe extraction
            #print(url)
            urls.append(url)
    #print(urls)
    urls = list(set(url for url in urls)) #remove duplicates
    #print(urls)
    return urls

#=======================
if __name__ == "__main__":

    google_news_url = ["https://news.google.com/search?tbm=nws&q=Alphabet+&hl=US&gl=US&tbs=qdr:w", "https://news.google.com/search?tbm=nws&q=GOOG.US&hl=US&gl=US&tbs=qdr:w"]
    url =[ "https://news.google.com/search?q=rheinmetall&hl=en-US&gl=US&ceid=US%3Aen"]
    url1 = ["https://news.google.com/search?q=rheinmetall&hl=de&gl=DE&ceid=DE:de&tbm=news"]


    result = download_google_news_urls(url)
    print(result)
