from jinja2 import Environment
from config import config

def url_templating(base_url, search_term, language="en", country="US", time_period="d"):
    """
    :param base_url: url to be used to construct final url
    :param search_term: what is to be search via Google
    :param language: default is "en", can be "de", "fr", "es" or any other language
    :param country: default is "US", can be "DE", "FR". pls note it is in capital letters
    :param time_period: default is "d", can be "w" or "m" or empty
    :return: a string with the constructed URL
    """

    # Definition of base URL for Google News Search
    base_url = base_url

    # Create Jinja template object
    env = Environment()

    # Define the Jinja template for the Google News Search URL
    news_url_template = env.from_string(
        base_url + "?tbm=nws&q={{ search_term|replace(' ', '+') }}"
        "&hl={{ language }}&gl={{ country }}{% if time_period %}&tbs=qdr:{{ time_period }}{% endif %}"
    )

    url_constructed = news_url_template.render(
        search_term=search_term, language=language, country=country, time_period=time_period
    )

    return url_constructed

#=======================
if __name__ == "__main__":
    base_url = config.BASE_URL
    # Example 1: Searching for "artificial intelligence" in English, US, past week
    url1 = url_templating(
        base_url=base_url, search_term="artificial intelligence", language="en", country="US", time_period="w"
    )
    print(f"URL 1: {url1}")

    # Example 2: Searching for "climate change" in French, France, past month
    url2 = url_templating(
        base_url=base_url, search_term="climate change", language="fr", country="FR", time_period="m"
    )
    print(f"URL 2: {url2}")

    url3 = url_templating(
        base_url=base_url, search_term="stocks", language="de", country="DE"
    )
    print(f"URL 3: {url3}")