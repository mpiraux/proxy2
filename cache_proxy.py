import hashlib
import os
import sqlite3
import threading
from datetime import datetime

from proxy2 import ProxyRequestHandler, test

if not os.path.exists('cache'):
    os.mkdir('cache')

thread_local = threading.local()


def get_db_conn():
    if not hasattr(thread_local, 'conn'):
        thread_local.conn = sqlite3.connect('database.sqlite', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        thread_local.conn.row_factory = sqlite3.Row
        thread_local.cursor = thread_local.conn.cursor()
    return thread_local.cursor, thread_local.conn


def setup_db():
    is_db_created = os.path.exists('database.sqlite')
    c, conn = get_db_conn()
    if not is_db_created:
        c.execute('''
            CREATE TABLE `resource` (
                `url`	TEXT NOT NULL UNIQUE,
                `headers` TEXT NOT NULL,
                `fetched_on`	TIMESTAMP NOT NULL,
                `last_accessed`	TIMESTAMP,
                `size`	INTEGER NOT NULL,
                PRIMARY KEY(`url`)
        )''')
        conn.commit()


def insert_resource(url, headers, body):
    c, conn = get_db_conn()
    c.execute('DELETE FROM resource WHERE url = ?', (url,))
    c.execute('''
        INSERT INTO `resource` VALUES (?, ?, ?, NULL, ?)
    ''', (url, str(headers), datetime.now(), len(body)))
    with open(os.path.join('cache', hashlib.sha256(url).hexdigest()), 'wb') as f:
        f.write(body)
    conn.commit()


def get_resource(url):
    c, conn = get_db_conn()
    c.execute('SELECT * FROM `resource` WHERE `url` = ?', (url,))
    resource = c.fetchone()
    if resource is not None:
        with open(os.path.join('cache', hashlib.sha256(url).hexdigest()), 'rb') as f:
            return resource['headers'], f.read()
    return None


class ProxyRequestHandlerWithCacheFallback(ProxyRequestHandler):
    def __init__(self, *args, **kwargs):
        ProxyRequestHandler.__init__(self, *args, **kwargs)

    def save_handler(self, req, req_body, res, res_body):
        pass

    def request_handler(self, req, req_body):
        pass

    def response_handler(self, req, req_body, res, res_body):
        # print ('resp', req, req.command, req.path, res.status, res.reason, res_body)
        if res.status == 200 and req.command == 'GET':
            print 'Put %s in cache' % req.path
            content_encoding = res.headers.get('Content-Encoding', 'identity')
            res_body = self.encode_content_body(res_body, content_encoding)
            res.headers['Content-Length'] = str(len(res_body))
            res.headers = self.filter_headers(res.headers)
            insert_resource(req.path, res.headers, res_body)

    def error_handler(self, req, req_body, res, res_body):
        print ('error', req, req.command, req.path)
        cached_resource = get_resource(req.path)

        if not res and cached_resource:
            print 'URL %s is in cache' % req.path
            headers, body = cached_resource

            self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'OK'))
            self.wfile.write(headers)
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            return True
        else:
            print 'URL %s not in cache' % req.path
            return False


if __name__ == '__main__':
    setup_db()
    test(HandlerClass=ProxyRequestHandlerWithCacheFallback)
