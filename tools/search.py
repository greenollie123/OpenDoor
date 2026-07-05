import urllib.parse
from html.parser import HTMLParser
import re

class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_title = False
        self.in_snippet = False
        self.current_title = []
        self.current_snippet = []
        self.current_url = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get('class', '')
        
        if tag == 'h2' and 'result__title' in cls:
            self.in_title = True
        elif tag == 'a' and 'result__a' in cls:
            for name, val in attrs:
                if name == 'href':
                    # Parse final URL out of the redirect link if present
                    if 'uddg=' in val:
                        parsed = urllib.parse.urlparse(val)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        self.current_url = query_params.get('uddg', [val])[0]
                    else:
                        self.current_url = val
        elif tag == 'a' and 'result__snippet' in cls:
            self.in_snippet = True

    def handle_endtag(self, tag):
        if tag == 'h2' and self.in_title:
            self.in_title = False
        elif tag == 'a' and self.in_snippet:
            self.in_snippet = False
            title_str = "".join(self.current_title).strip()
            snippet_str = "".join(self.current_snippet).strip()
            snippet_str = re.sub(r'\s+', ' ', snippet_str) # clean spacing
            if title_str or self.current_url:
                self.results.append({
                    "title": title_str,
                    "url": self.current_url,
                    "snippet": snippet_str
                })
            self.current_title = []
            self.current_snippet = []
            self.current_url = None

    def handle_data(self, data):
        if self.in_title:
            self.current_title.append(data)
        elif self.in_snippet:
            self.current_snippet.append(data)

@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information matching the query.
    
    Args:
        query: The search query to look up.
        max_results: The maximum number of results to return (default is 5).
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.post(url, data={"q": query}, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Error: Unable to fetch search results (Status code {response.status_code})"
        
        parser = DDGParser()
        parser.feed(response.text)
        
        if not parser.results:
            return "No results found."
            
        formatted_results = []
        for i, res in enumerate(parser.results[:max_results], 1):
            formatted_results.append(
                f"{i}. Title: {res['title']}\n"
                f"   URL: {res['url']}\n"
                f"   Snippet: {res['snippet']}\n"
            )
        return "\n".join(formatted_results)
    except Exception as e:
        return f"Error occurred during search: {e}"