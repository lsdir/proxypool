#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import logging

import retrying
import execjs

from config import SPIDER_MAX_ATTEMPT_NUMBER
from util.http import headers
from util.utils import get_current_time_str
from spider.getproxy import Plugin, PROXY_PROTOCOL_HTTP, PROXY_ANONYMITY_HIGH_ANONYMOUS

logger = logging.getLogger(__name__)


class Proxy(Plugin):
    def __init__(self):
        Plugin.__init__(self)

        self.name = '快代理'
        self.protocol = PROXY_PROTOCOL_HTTP
        self.anonymity = PROXY_ANONYMITY_HIGH_ANONYMOUS

        self.host = 'www.kuaidaili.com'
        self.url_template = 'http://www.kuaidaili.com/free/inha/{page}/'
        self.re_ip_pattern = re.compile(r">(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>")
        self.re_port_pattern = re.compile(r">(\d{1,5})</td>")
        self.cookie = None

    @retrying.retry(stop_max_attempt_number=SPIDER_MAX_ATTEMPT_NUMBER)
    def _extract_proxy(self, page_num):
        try:
            full_url = self.url_template.format(page=page_num)
            rp = self.session.get(url=full_url, headers=headers(host=self.host, cookie=self.cookie), timeout=10)
            if rp.status_code == 521:
                self._set_cookies(rp.text)
                self._log(logger, 'extract data error', full_url, 'response javascript code')
                self._need_retry()
        except Exception as e:
            self._log(logger, 'request error', full_url, str(e))
            self._need_retry()

        re_ip_result = self.re_ip_pattern.findall(rp.text)
        re_port_result = self.re_port_pattern.findall(rp.text)

        if not re_ip_result or not re_port_result:
            self._log(logger, 'extract data error', full_url, 'find no proxy data in web page')
            self._need_retry()

        if len(re_ip_result) != len(re_port_result):
            self._log(logger, 'extract data error', full_url,
                      'the number of hosts and ports extracted from web page are different')
            self._need_retry()

        result_list = zip(re_ip_result, re_port_result)

        return [{'host': host, 'port': port, 'from': self.name, 'grab_time': get_current_time_str()} for host, port in
                result_list]

    def _set_cookies(self, text):
        try:
            js_function_name = re.findall(r'setTimeout\("(.*?)\(', text)[0]
            js_args_value = re.findall(r'setTimeout\(.*?\((.*?)\)', text)[0]
            js_code = re.findall(r'(function.*?)</script>', text)[0].replace('eval("qo=eval;qo(po);");', 'return po;')
        except Exception as e:
            logger.error('parse javascript code failed, error: %s' % str(e))
            return

        try:
            exe = execjs.compile(js_code)
            ret_text = exe.call(js_function_name, js_args_value)
            cookies_str = re.findall(r"='(.*?);", ret_text)[0]
        except Exception as e:
            logger.error('execute javascript code failed, error: %s' % str(e))
            return

        self.cookie = cookies_str

    def start(self):
        for page in range(1, 10):
            try:
                page_result = self._extract_proxy(page)
                if page_result:
                    self.result.extend(page_result)
                time.sleep(3)
            except Exception as e:
                logger.error(str(e))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    p = Proxy()
    p.start()
    for i in p.result:
        print(i)
