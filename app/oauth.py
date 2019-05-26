import json
import time
from rauth import OAuth1Service, OAuth2Service
from flask import current_app, url_for, request, redirect

from bs4 import BeautifulSoup as bs

class OAuthSignIn(object): # below class inherits from this one
    providers = None

    def __init__(self, provider_name):
        self.provider_name = provider_name
        credentials = current_app.config['OAUTH_CREDENTIALS'][provider_name]
        self.consumer_id = credentials['id']
        self.consumer_secret = credentials['secret']

    def authorize(self):
        pass

    def callback(self):
        pass

    def get_callback_url(self):
        return url_for('oauth_callback', provider=self.provider_name,
                       _external=True)

    @classmethod
    def get_provider(self, provider_name):
        if self.providers is None:
            self.providers = {}
            for provider_class in self.__subclasses__():
                provider = provider_class()
                self.providers[provider.provider_name] = provider
        return self.providers[provider_name]


class ORCIDSignIn(OAuthSignIn):
    def __init__(self):
        super(ORCIDSignIn, self).__init__('orcid')
        self.service = OAuth2Service(
            name='orcid',
            client_id=self.consumer_id,
            client_secret=self.consumer_secret,
            authorize_url='https://orcid.org/oauth/authorize',
            access_token_url='https://orcid.org/oauth/token',
            base_url='https://orcid.org/oauth'
        )


    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='/authenticate',
            response_type='code',
            redirect_uri=self.get_callback_url())
        )

    def callback(self):
        print('defining function')
        def decode_json(payload):
            return json.loads(payload.decode('utf-8'))
        print('function defined')
        if 'code' not in request.args:
            print('ERROR code not found')
            return None, None, None
        print('code found', request.args['code'])
        print(self.provider_name, self.get_callback_url())

        ## ERROR - PROBLEM IS WITH THIS LINE!!!
        oauth_session = self.service.get_auth_session(
            data={'code': request.args['code'],
                  'grant_type': 'authorization_code',
                  'redirect_uri': self.get_callback_url()},
            decoder=decode_json
        )
        print(oauth_session)
        print('Oauth session created successfully')
        response = self.service.access_token_response.json()
        # print('RESPONSE', response)
        ## EXAMPLE of response
        """
        b'{"access_token":"blahblahblah",
        "token_type":"bearer",
        "refresh_token":"blahblahblah",
        "expires_in":631138518,
        "scope":"/authenticate",
        "name":"Adam Day",
        "orcid":"0000-0002-8529-9990"}'
        """
        # orcid = response['orcid']

        # get the xml record. Might be smarter to parse this in a separate operation
        # url_record = 'https://pub.orcid.org/v2.0/'+orcid+'/record'
        # record = oauth_session.get(url_record).text #, params={'format':'json'})#.json()
        return response #, record
