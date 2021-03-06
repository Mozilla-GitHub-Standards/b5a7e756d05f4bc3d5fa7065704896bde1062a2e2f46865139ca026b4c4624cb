import simplejson as json

def test_publishing_massive_content_results_in_error():
    res = app.post('/publish', {
        'html': '<p>' + ('!' * wsgiapp.settings.MAX_PAYLOAD_SIZE) + '</p>',
         'original-url': 'http://bar.com/',
    }, status=413)
    equals(res.status, '413 Request Entity Too Large')

def test_publishing_malformed_body_results_in_error():
    res = app.post('/publish', 'garbage', status=400)
    equals(res.status, '400 Bad Request')
    equals(res.body, 'Unrecognized content.')

def test_publishing_without_body_results_in_error():
    res = app.post('/publish', status=411)
    equals(res.status, '411 Length Required')

def test_publishing_malformed_json_results_in_error():
    res = app.post('/publish', {'json': 'lol'}, status=400)
    equals(res.status, '400 Bad Request')
    equals(res.body, 'Malformed JSON.')

def test_publishing_without_html_results_in_error():
    res = app.post('/publish', {'hi': 'there'}, status=400)
    equals(res.status, '400 Bad Request')
    equals(res.body, 'Unrecognized content.')

def test_publishing_with_empty_html_results_in_error():
    res = app.post('/publish', {'html': '  '}, status=400)
    equals(res.status, '400 Bad Request')
    equals(res.body, 'Unrecognized content.')

def test_using_unsupported_methods_results_in_error():
    res = app.put('/publish', status=405)
    equals(res.status, '405 Method Not Allowed')

def test_get_metadata_on_nonexistent_document_fails():
    res = app.get('/metadata/nonexistent', status=404)
    equals(res.status, '404 Not Found')

def test_get_nonexistent_path_fails():
    res = app.get('/nonexistent', status=404)
    equals(res.status, '404 Not Found')

def post_sample_doc():
    html = u'<p>hello\u2026</p>'
    res = app.post('/publish', {
        'html': html.encode('utf-8'),
        'original-url': 'http://bar.com/',
    })
    return res

def post_sample_json():
    content = json.dumps({'hi': u'hello\u2026'})
    if not isinstance(content, str):
        raise Exception('Expected JSON dump to be a string')
    res = app.post('/publish', {
        'json': content,
        'original-url': 'http://bar.com/',
    })
    return res

def test_publishing_works():
    res = post_sample_doc()
    equals(res.status, '200 OK')
    equals(res.json['published-url'], 'http://pages.foo.org/beoab')

def test_publishing_json_works():
    res = post_sample_json()
    equals(res.status, '200 OK')
    equals(res.json['published-url'], 'http://pages.foo.org/beoab')

def test_get_metadata_works():
    post_sample_doc()
    res = app.get('/metadata/beoab')
    equals(res.status, '200 OK')
    equals(res.json['original-url'], 'http://bar.com/')
    equals(res.json['published-url'], 'http://pages.foo.org/beoab')
    equals(res.json['created'], 'Mon, 19 Sep 2011 16:21:30 GMT')

def test_fetching_published_html_works():
    post_sample_doc()
    content, content_type = wsgiapp.storage.get_content('beoab')
    equals(content, u'<p>hello\u2026</p>'.encode('utf-8'))
    equals(content_type, 'text/html; charset=utf-8')

def test_fetching_published_json_works():
    post_sample_json()
    content, content_type = wsgiapp.storage.get_content('beoab')
    equals(content, json.dumps({'hi': u'hello\u2026'}))
    equals(content_type, 'application/json')

def test_ppx_server():
    res = app.get('/ppx-server')
    equals(res.status, '200 OK')
    if '<!DOCTYPE html>' not in res.body:
        raise AssertionError('could not find <!DOCTYPE html>')

def test_data_is_not_spidered():
    res = app.get('/robots.txt')
    equals(res.status, '200 OK')
    equals(res.body, "User-agent: *\r\nDisallow: /\r\n")

def test_cross_origin_resource_sharing():
    """
    For more info, see https://developer.mozilla.org/en/HTTP_access_control
    """

    res = app.request('/publish', method='OPTIONS')
    equals(res.headers['Access-Control-Allow-Origin'], '*')
    # A custom header that jQuery ajax requests seem to contain.
    equals(res.headers['Access-Control-Allow-Headers'], 'x-requested-with')
    equals(res.headers['Access-Control-Allow-Methods'], 'OPTIONS, GET, POST')

def test_multiplexing_integration():
    from test_multiplexer import Multiplexer, sample_app_1
    
    mp = Multiplexer(sample_app_1, 'more', {
        'foopages': wsgiapp
    })
    app = TestApp(mp)
    app.post('/more/foopages/publish', status=411)
    res = app.get('/more/foopages/blarg', status=404)
    equals(res.body, "not found: /more/foopages/blarg")
    post_sample_doc()
    res = app.get('/more/foopages/metadata/beoab')

# Test setup, collection, and helpers

import unittest

from webtest import TestApp
from hackpub.app import Application

app = None
wsgiapp = None

class FakeStorage(object):
    def __init__(self):
        self._keys = ['beoab']
        self._storage = {}
        self._urlbase = 'http://pages.foo.org/'

    def get_content(self, key):
        if key in self._storage:
            return (self._storage[key]['content'],
                    self._storage[key]['content_type'])
        return None, None

    def get_metadata(self, key):
        if key in self._storage:
            return self._storage[key]['metadata'].copy()
        return None

    def create(self, content, mimetype, metadata):
        key = self._keys.pop()
        metadata = metadata.copy()
        metadata['published-url'] = self._urlbase + key
        self._storage[key] = dict(
            content=content,
            content_type=mimetype,
            metadata=metadata.copy()
        )
        return metadata['published-url']

def equals(a, b):
    if a != b:
        raise AssertionError('%s != %s' % (repr(a), repr(b)))

def load_tests(loader, tests, pattern):    
    globs = globals()

    class Settings(object):
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def now():
        return 1316449290.594553

    def setup():
        global app
        global wsgiapp

        storage = FakeStorage()
        settings = Settings(
            ALLOW_ORIGINS='*',
            MAX_PAYLOAD_SIZE=5000,
            ENABLE_PPX=True
        )
        wsgiapp = Application(settings, storage, now)
        app = TestApp(wsgiapp)

    if pattern is None:
        pattern = ''
    tests = [
        unittest.FunctionTestCase(globs[name], setUp=setup)
        for name in globs
        if name.startswith('test_') and pattern in name
    ]
    suite = unittest.TestSuite()
    suite.addTests(tests)
    return suite
