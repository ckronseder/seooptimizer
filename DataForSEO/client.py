import logging
import requests
from base64 import b64encode
import re
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from config import config

logger = logging.getLogger("DataForSEO")

class RestClient:
    domain = "https://api.dataforseo.com" # Changed to include https:// for requests

    def __init__(self, username, password):
        self.username = username
        self.password = password
        # Basic authentication header, used across all requests
        self.auth_headers = {
            'Authorization': 'Basic %s' % b64encode(
                (f"{self.username}:{self.password}").encode("ascii")
            ).decode("ascii"),
            'Content-Encoding': 'gzip', # Keep if API expects gzipped content
            'Content-Type': 'application/json' # Often required for POST requests
        }

    def request(self, path, method, data=None):
        """
        Sends an HTTP request to the DataForSEO API using the requests library.

        Args:
            path (str): The API endpoint path (e.g., '/v3/serp/google/organic/live/advanced').
            method (str): The HTTP method ('GET' or 'POST').
            data (dict or str, optional): The request body for POST requests. Defaults to None.

        Returns:
            dict: The JSON response from the API.
        """
        url = f"{self.domain}{path}"
        headers = self.auth_headers.copy() # Use a copy to modify if needed per request

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30) # Add timeout
            elif method.upper() == 'POST':
                # requests handles JSON serialization for 'json' parameter
                if isinstance(data, str):
                    # If data is already a string (e.g., pre-dumped JSON)
                    response = requests.post(url, headers=headers, data=data, timeout=30)
                else:
                    # requests will automatically set Content-Type to application/json
                    # and serialize the dict to JSON if 'json' parameter is used.
                    response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json() # Automatically parses JSON response

        except requests.exceptions.Timeout as e:
            logger.error("Request timed out for %s: %s", url, e)
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Error during request to %s: %s", url, e)
            if e.response is not None:
                logger.error("Response status: %s", e.response.status_code)
                try:
                    logger.error("Response body: %s", e.response.text)
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error("An unexpected error occurred: %s", e)
            raise

    def get(self, path):
        """
        Sends a GET request.
        """
        return self.request(path, 'GET')

    def post(self, path, data):
        """
        Sends a POST request.
        """
        # Data will be handled by the request method
        return self.request(path, 'POST', data)

def extract_keywords_from_dataforseo_response(json_data):
    """
    Extracts the 'keyword' values from the 'result' array within the 'tasks' array
    of a DataForSEO API JSON response.

    Args:
        json_data (dict): The parsed JSON response from DataForSEO.

    Returns:
        list: A list of keyword strings, or an empty list if no keywords are found
              or the structure is not as expected.
    this is very much hardcoded
    """
    keywords = []
    try:
        # Navigate through the JSON structure: tasks -> result -> items
        items = json_data["tasks"][0]["result"][0]["items"]
        if items:
            for item in items:
                keyword = item["keyword"]
                level = item["keyword_info"]["competition_level"]
                if keyword:
                    keywords.append(keyword)
    except Exception as e:
        logger.error("Error parsing JSON data: %s", e)

    return keywords


def consolidate_keywords(keyword_list):
    """
    Consolidates a list of keywords by normalizing them (lowercase, remove special
    characters/hyphens, extra spaces, lemmatization) and then removing duplicates,
    including those with different word order or pluralization/tenses.

    Args:
        keyword_list (list): A list of keyword strings.

    Returns:
        list: A new list of unique, consolidated keyword strings.
    """
    consolidated_set = set()
    lemmatizer = WordNetLemmatizer()  # Initialize lemmatizer outside the loop

    for keyword in keyword_list:
        # 1. Convert to lowercase
        normalized_keyword = keyword.lower()

        # 2. Replace hyphens with spaces (e.g., "dubai-schokolade" -> "dubai schokolade")
        normalized_keyword = normalized_keyword.replace('-', ' ')

        # 3. Remove non-alphanumeric characters except spaces (e.g., "#", ":")
        # and replace them with a single space to avoid concatenating words
        normalized_keyword = re.sub(r'[^\w\s]', ' ', normalized_keyword)

        # 4. Replace multiple spaces with a single space and strip leading/trailing spaces
        normalized_keyword = re.sub(r'\s+', ' ', normalized_keyword).strip()

        # 5. Lemmatize each word in the keyword phrase
        # Split the phrase into words, lemmatize each, and then join them back
        lemmatized_words = [lemmatizer.lemmatize(word) for word in word_tokenize(normalized_keyword)]

        # 6. Sort the lemmatized words alphabetically and then join them back.
        # This handles variations in word order (e.g., "lidl dubai schokolade" and "dubai schokolade lidl")
        sorted_words_combined = sorted(lemmatized_words)
        final_normalized_keyword = ' '.join(sorted_words_combined)

        # 7. Add to set to handle duplicates
        if final_normalized_keyword:  # Ensure not to add empty strings
            consolidated_set.add(final_normalized_keyword)

    # Sort the consolidated keywords for consistent output (optional)
    return sorted(list(consolidated_set))

# Example Usage (assuming you have your username and password for DataForSEO)
if __name__ == "__main__":
    # Replace with your actual DataForSEO credentials
    YOUR_USERNAME = config.SEO_USERNAME
    YOUR_PASSWORD = config.SEO_PASSWORD

    client = RestClient(YOUR_USERNAME, YOUR_PASSWORD)
    """
    # Example GET request (check DataForSEO API documentation for actual paths)
    # This is a placeholder path, replace with a valid DataForSEO GET endpoint
    try:
        print("Attempting GET request...")
        get_response = client.get("/v3/dataforseo_labs/google/keyword_suggestions/live") # Example status endpoint
        print("\nGET Response:")
        print(json.dumps(get_response, indent=2))
    except Exception as e:
        print(f"GET request failed: {e}")

    print("\n" + "="*50 + "\n")
    """
    # Example POST request (check DataForSEO API documentation for actual paths and data structure)
    # This is a placeholder for a POST request body, replace with a valid DataForSEO POST request body
    post_data = [
        {
            "language_code": "de",
            "location_code": 2276,  # Germany
            "keyword": "Schokolade",
            "limit": 50
        }
    ]
    # Example POST endpoint
    post_path = config.SEO_post_path

    try:
        print("Attempting POST request...")
        post_response = client.post(post_path, post_data)
        print("\nPOST Response:")
        #print(json.dumps(post_response, indent=2))

        # post_response is already a dictionary from client.post (which calls response.json())
        keywords_list = extract_keywords_from_dataforseo_response(post_response)

        consolidated_keywords_list = consolidate_keywords(keywords_list)

        print("\nExtracted Keywords:")
        for keyword in consolidated_keywords_list:
            print(f"- {keyword}")

        print(f"\nTotal keywords extracted: {len(consolidated_keywords_list)}")
    except Exception as e:
        print(f"POST request failed: {e}")


