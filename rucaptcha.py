import requests


class RuCaptcha:
    def __init__(self,
                 apikey: str):
        self.apikey = apikey

    def send(self,
             site_key: str,
             page_url: str,
             action: str = 'verify'):
        return requests.get(f'http://rucaptcha.com/in.php?key={self.apikey}&method=userrecaptcha&version=v3'
                            f'&action={action}&min_score=0.3&googlekey={site_key}&pageurl={page_url}&json=1').json()

    def result(self,
               request: str):
        return requests.get(f'http://rucaptcha.com/res.php?key={self.apikey}&action=get&json=1&id={request}').json()

    def report_good(self,
                    request: str):
        return requests.get(f'http://rucaptcha.com/res.php?key={self.apikey}&action=reportgood&id={request}')

    def report_bad(self,
                   request: str):
        return requests.get(f'http://rucaptcha.com/res.php?key={self.apikey}&action=reportbad&id={request}')
