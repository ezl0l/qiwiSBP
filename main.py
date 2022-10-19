import base64
import functools
import hashlib
import json
import time
import requests

from rucaptcha import RuCaptcha


class Qiwi:
    def __init__(self):
        self.session = requests.session()
        self.session.request = functools.partial(self.session.request, timeout=10)

    def anonymous_token(self):
        return self.session.post('https://qiwi.com/oauth/token',
                                 data={
                                     'grant_type': 'anonymous',
                                     'client_id': 'anonymous'
                                 }).json()

    def token(self,
              username: str,
              password: str,
              anonymous_token_head: str,
              client_secret: str = 'P0CGsaulvHy9'):
        return self.session.post('https://qiwi.com/oauth/token',
                                 data={
                                     'token_type': 'headtail',
                                     'grant_type': 'password',
                                     'client_id': 'web-qw',
                                     'client_secret': client_secret,
                                     'username': username,
                                     'password': password,
                                     'recaptcha': '',
                                     'anonymous_token_head': anonymous_token_head
                                 }).json()

    @staticmethod
    def to_qiwi_wallet(access_token: str,
                       phone: str,
                       amount: float):
        return requests.post('https://edge.qiwi.com/sinap/api/v2/terms/99/payments',
                             json={
                                 'id': str(round(time.time() * 1000)),
                                 'sum': {
                                     'amount': round(amount, 2),
                                     'currency': '643'
                                 },
                                 'paymentMethod': {
                                     'type': 'Account',
                                     'accountId': '643'
                                 },
                                 'fields': {
                                     'account': phone
                                 }
                             },
                             headers={
                                 'Accept': 'application/json',
                                 'Authorization': f'Bearer {access_token}'
                             }).json()

    @staticmethod
    def balances(access_token: str,
                 person_id: str):
        return requests.get(f'https://edge.qiwi.com/funding-sources/v2/persons/{person_id}/accounts',
                            headers={
                                'Accept': 'application/json',
                                'Authorization': f'Bearer {access_token}'
                            }).json()


class SBP:
    qiwi_recaptcha_action = 'CREATE_PAYMENT'
    qiwi_site_key = '6LczddIZAAAAADtx_azLKiG2CPqb6JvqYQorAqvG'
    qiwi_sbp_url = 'https://qiwi.com/payment/form/36699'

    def __init__(self,
                 sender_phone: str,
                 sender_password: str,
                 rucaptcha: RuCaptcha = None):
        self.sender_phone = sender_phone

        self.qiwi = Qiwi()

        anonymous_token = self.qiwi.anonymous_token()
        token = self.qiwi.token(sender_phone,
                                sender_password,
                                anonymous_token['access_token'])
        self.b64_token_header = base64.b64encode(('web-qw:%s' % token['access_token']).encode()).decode()

        self.ga_cid = hashlib.md5(sender_phone.encode()).hexdigest()[:8]
        self.browser_ua_crc = hashlib.md5((sender_phone + '1').encode()).hexdigest()[:8]

        self.rucaptcha = rucaptcha

    def transfer(self,
                 recipient_phone: str,
                 amount: float,
                 comment: str = ''):
        def get_field(array: list, key: str):
            for v in array:
                if v['name'] == key:
                    return v['value']
            return None

        amount = str(round(amount, 2))

        r = self.qiwi.session.post(
            'https://edge.qiwi.com/sinap/api/refs/d2490967-10fa-4b76-aa55-e302421a3fe8/containers',
            json={'senderId': self.sender_phone,
                  'account': recipient_phone},
            headers={'Accept': 'application/vnd.qiwi.v1+json',
                     'Authorization': f'TokenHeadV2 {self.b64_token_header}'}).json()
        if 'elements' not in r:
            return False

        receiver_bank_member_id = get_field(r['elements'], 'receiverBankMemberId')

        r = self.qiwi.session.post(
            'https://edge.qiwi.com/sinap/api/refs/f3dd49ea-4e7e-483d-a58b-d44f26a41877/containers',
            json={'senderId': self.sender_phone,
                  'account': recipient_phone,
                  'receiverBankMemberId': receiver_bank_member_id,
                  'amount': amount,
                  'udid': ' ',
                  'gaCid': self.ga_cid},
            headers={'Accept': 'application/vnd.qiwi.v1+json',
                     'Authorization': f'TokenHeadV2 {self.b64_token_header}'}).json()
        if 'elements' not in r:
            return False

        recaptcha_value = ''

        j = {"id": str(round(time.time() * 1000)),
             "sum": {
                 "amount": amount,
                 "currency": "643"
             },
             "paymentMethod": {
                 "accountId": "643",
                 "type": "Account"
             },
             "comment": comment,
             "fields": {
                 "sinap-form-version": "qw::36699, 4",
                 "workaround": "1",
                 "senderId": self.sender_phone,
                 "errorMessage": "Включите исходящие платежи в разделе \"Настройки\"",
                 "identificationStatus": "verified",
                 "auth": "true",
                 "outgoingPaymentsEnabled": "true",
                 "account": self.sender_phone,
                 "receiverBankMemberId": receiver_bank_member_id,  # tinkoff
                 "limitInfo": "Не более 3500 рублей",
                 "amount": str(amount),
                 "gaCid": self.ga_cid,
                 "udid": " ",
                 "prvTxnId": get_field(r['elements'], 'prvTxnId'),
                 "senderBankAccount": get_field(r['elements'], 'senderBankAccount'),
                 "receiverBankMemberName": get_field(r['elements'], 'receiverBankMemberName'),
                 "receiverPAM": get_field(r['elements'], 'receiverPAM'),
                 "prvTxnDate": get_field(r['elements'], 'prvTxnDate'),
                 "is_sbp": "true",
                 "browser_user_agent_crc": self.browser_ua_crc,
                 "ga_cid": self.ga_cid,
                 "recaptcha3Value": recaptcha_value
             }
             }

        r = self.qiwi.session.post('https://edge.qiwi.com/sinap/api/terms/36699/payments',
                                   data=json.dumps(j, ensure_ascii=False).encode('utf-8'),
                                   headers={'Accept': 'application/vnd.qiwi.v2+json',
                                            'Content-Type': 'application/json',
                                            'Authorization': f'TokenHeadV2 {self.b64_token_header}',
                                            'X-Application-Id': '0ec0da91-65ee-496b-86d7-c07afc987007',
                                            'X-Application-Secret': '66f8109f-d6df-49c6-ade9-5692a0b6d0a1'
                                            }).json()
        print(r)

        return 'transaction' in r and 'state' in r['transaction'] and r['transaction']['state']['code'] == 'Accepted'


if __name__ == '__main__':
    sender1_phone = 'номер'
    sender1_password = 'пасс'

    recipient_phone = 'куда кидать'

    amount = 100

    sbp = SBP(sender1_phone, sender1_password)
    if sbp.transfer(recipient_phone, amount):
        print('Успешно!')
    else:
        print('Произошла ошибка!')
