DEFAULT_SEARCH_KEYS = ['title', 'description', 'author', 'name']
METADATA_INDEXES = ['title', 'description', 'author']
DEFAULT_SETTINGS = {'search_by': DEFAULT_SEARCH_KEYS}
DEFAULT_WEIGHTS = {'name': 1.5, 'title': 1.25, 'description': 1.0, 'author': 1.25}
MAX_RETURNED_RESULTS = 25
CACHE_SIZE = 1000
MAX_SD_TRIES = 1
FILTERED = ['socialengineering']