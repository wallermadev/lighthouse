import logging.handlers
from twisted.internet import defer, threads
from fuzzywuzzy import process
from lighthouse.conf import CACHE_SIZE, MAX_RETURNED_RESULTS, DEFAULT_WEIGHTS
from lighthouse.conf import METADATA_INDEXES, DEFAULT_SETTINGS, FILTERED

log = logging.getLogger()


class FuzzyNameIndex(object):
    def __init__(self, updater):
        self.index = 'name'
        self.updater = updater
        self.max_cache = CACHE_SIZE
        self.results_cache = {}
        self.search_cache = []

    def search(self, value, max_results=100, settings=None):
        d = self.get_search_results(value, max_results, settings)
        return d

    def get_search_results(self, search, max_results, settings):
        if settings:
            force = settings.get('force', False)
        else:
            force = False

        if not force:
            if search in self.results_cache:
                return defer.succeed(self.results_cache[search])
        return self.process_search(search, max_results)

    def process_search(self, search, max_results):
        return self._process_search(search, max_results)

    def _process_search(self, search, max_results):
        d = threads.deferToThread(
            process.extract,
            search,
            self.updater.metadata.keys(),
            limit=max_results
        )
        d.addCallback(lambda r: self._update_cache(search, r))
        return d

    def _update_cache(self, k, r):
        if len(self.search_cache) > self.max_cache or k in self.results_cache:
            del self.results_cache[self.search_cache.pop()]
        self.search_cache.reverse()
        self.search_cache.append(k)
        self.search_cache.reverse()
        self.results_cache.update({k: r})
        return r


class FuzzyMetadataIndex(object):
    def __init__(self, index, updater):
        self.index = index
        self.updater = updater
        self.max_cache = CACHE_SIZE
        self.results_cache = {}
        self.search_cache = []

    def search(self, value, max_results=100, settings=None):
        d = self.get_search_results(value, max_results, settings)
        return d

    def get_search_results(self, value, max_results, settings):
        if settings:
            force = settings.get('force', False)
        else:
            force = False

        if not force:
            if value in self.results_cache:
                return defer.succeed(self.results_cache[value])
        return self.process_search(value, max_results, settings)

    def process_search(self, search, max_results, settings):
        return self._process_search(search, max_results, settings)

    def _process_search(self, search, max_results, settings):
        d = threads.deferToThread(
            process.extract,
            search,
            self.updater.metadata.keys(),
            limit=max_results,
            processor=lambda x: self.updater.metadata[x][self.index]
        )
        d.addCallback(lambda r: self._update_cache(search, r))
        return d

    def _update_cache(self, k, r):
        if len(self.search_cache) > self.max_cache or k in self.results_cache:
            del self.results_cache[self.search_cache.pop()]
        self.search_cache.reverse()
        self.search_cache.append(k)
        self.search_cache.reverse()
        self.results_cache.update({k: r})
        return r


class LighthouseSearch(object):
    def __init__(self, updater):
        self.updater = updater
        self.indexes = {key: FuzzyMetadataIndex(key, self.updater) for key in METADATA_INDEXES}
        self.indexes.update({'name': FuzzyNameIndex(self.updater)})

    def _get_dict_for_return(self, name):
        r = {
            'name': name,
            'value': self.updater.metadata[name],
            'cost': self.updater.cost_and_availability[name]['cost'],
            'available': self.updater.cost_and_availability[name]['available'],
        }
        return r

    def search(self, search, settings=DEFAULT_SETTINGS):
        def search_by(search, settings):
            search_keys = settings.get('search_by')
            d = defer.DeferredList([self.indexes[search_by].search(search) for search_by in search_keys])
            d.addCallback(lambda r: {search_keys[i]: r[i][1] for i in range(len(search_keys))})
            return d

        def _apply_weights(results):
            r = {}
            for k in results:
                applied_weights = []
                for v in results[k]:
                    applied_weights.append((v[0], v[1] * DEFAULT_WEIGHTS[k]))
                r.update({k: applied_weights})
            return r

        def _sort(results):
            return sorted(results, key=lambda x: x[1], reverse=True)

        def _combine(results):
            t = []
            for s in results:
                t += results[s]
            r = []
            for i in t:
                check = [j for j in r if j[0] == i[0]]
                if check:
                    already_in_results = check[0]
                else:
                    already_in_results = False
                if not i[0] in FILTERED:
                    if not already_in_results:
                        r.append(i)
                    elif i[1] > already_in_results[1]:
                        r.remove(already_in_results)
                        r.append(i)
            return r

        def _format(results):
            shortened = results[:min(MAX_RETURNED_RESULTS, len(results) - 1)]
            final = []
            for r in shortened:
                final.append(self._get_dict_for_return(r[0]))
            return final

        d = search_by(search, settings)
        d.addCallback(_apply_weights)
        d.addCallback(_combine)
        d.addCallback(_sort)
        d.addCallback(_format)
        return d
