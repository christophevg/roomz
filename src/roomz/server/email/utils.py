"""
Utilities for email operations.
"""

import urllib.parse


def extract_token_from_url(url: str) -> str:
  """
  Extract the 'token' query parameter from a magic link URL.

  Args:
    url: The magic link URL to parse.

  Returns:
    The token value if found, otherwise an empty string.
  """
  parsed = urllib.parse.urlparse(url)
  query_params = urllib.parse.parse_qs(parsed.query)
  return query_params.get("token", [""])[0]
