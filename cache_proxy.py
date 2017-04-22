import os

from proxy2 import ProxyRequestHandler, test

if not os.path.exists('cache'):
    os.mkdir('cache')

cache = {}


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
            cache[req.path] = (res.headers, res_body)

    def error_handler(self, req, req_body, res, res_body):
        print ('error', req, req.command, req.path)
        if res is None and req.path in cache:
            print 'URL %s is in cache' % req.path
            headers, body = cache[req.path]
            self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'OK'))
            for line in self.filter_headers(headers).headers:
                self.wfile.write(line)
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            return True
        else:
            print 'URL %s not in cache' % req.path
            return False


if __name__ == '__main__':
    test(HandlerClass=ProxyRequestHandlerWithCacheFallback)
