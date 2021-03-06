# This script is heavily inspired by
# https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/iap/make_iap_request.py

import google.auth
import google.auth.app_engine
import google.auth.compute_engine.credentials
import google.auth.iam
from google.auth.transport.requests import Request
import google.oauth2.credentials
import google.oauth2.service_account
import requests
import requests_toolbelt.adapters.appengine
import sys

# Please rewrite these values to yours
REFLECT_SERVICE_HOSTNAME = 'myserver.example.com'
IAP_CLIENT_ID = '657424576728-3t5uiqg5ktqj5hqk3j45btq5uq98faos.apps.googleusercontent.com'
IAP_APP_ID = 'gcp-project'
IAP_PROJECT_NUMBER = '657424576728'

IAM_SCOPE = 'https://www.googleapis.com/auth/iam'
OAUTH_TOKEN_URI = 'https://www.googleapis.com/oauth2/v4/token'

def make_iap_request(url, client_id):
    from google.oauth2 import service_account
    credentials = service_account.Credentials.from_service_account_file('./gcp-project-14a614b2955c.json')
    bootstrap_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/cloud-platform'])

    # For service account's using the Compute Engine metadata service,
    # service_account_email isn't available until refresh is called.
    bootstrap_credentials.refresh(Request())

    signer_email = bootstrap_credentials.service_account_email
    if isinstance(bootstrap_credentials,
                  google.auth.compute_engine.credentials.Credentials):
        signer = google.auth.iam.Signer(
            Request(), bootstrap_credentials, signer_email)
    else:
        signer = bootstrap_credentials.signer

    service_account_credentials = google.oauth2.service_account.Credentials(
        signer, signer_email, token_uri=OAUTH_TOKEN_URI, additional_claims={
            'target_audience': client_id
        })

    # service_account_credentials gives us a JWT signed by the service
    # account. Next, we use that to obtain an OpenID Connect token,
    # which is a JWT signed by Google.
    google_open_id_connect_token = get_google_open_id_connect_token(
        service_account_credentials)

    # Fetch the Identity-Aware Proxy-protected URL, including an
    # Authorization header containing "Bearer " followed by a
    # Google-issued OpenID Connect token for the service account.
    resp = requests.get(
        url,
        headers={'Authorization': 'Bearer {}'.format(
            google_open_id_connect_token)})
    if resp.status_code == 403:
        raise Exception('Service account {} does not have permission to '
                        'access the IAP-protected application.'.format(
                            signer_email))
    elif resp.status_code != 200:
        raise Exception(
            'Bad response from application: {!r} / {!r} / {!r}'.format(
                resp.status_code, resp.headers, resp.text))
    else:
        return resp.text


def get_google_open_id_connect_token(service_account_credentials):
    """Get an OpenID Connect token issued by Google for the service account.

    This function:

      1. Generates a JWT signed with the service account's private key
         containing a special "target_audience" claim.

      2. Sends it to the OAUTH_TOKEN_URI endpoint. Because the JWT in #1
         has a target_audience claim, that endpoint will respond with
         an OpenID Connect token for the service account -- in other words,
         a JWT signed by *Google*. The aud claim in this JWT will be
         set to the value from the target_audience claim in #1.

    For more information, see
    https://developers.google.com/identity/protocols/OAuth2ServiceAccount .
    The HTTP/REST example on that page describes the JWT structure and
    demonstrates how to call the token endpoint. (The example on that page
    shows how to get an OAuth2 access token; this code is using a
    modified version of it to get an OpenID Connect token.)
    """

    service_account_jwt = (
        service_account_credentials._make_authorization_grant_assertion())
    request = google.auth.transport.requests.Request()
    body = {
        'assertion': service_account_jwt,
        'grant_type': google.oauth2._client._JWT_GRANT_TYPE,
    }
    token_response = google.oauth2._client._token_endpoint_request(request, OAUTH_TOKEN_URI, body)
    return token_response['id_token']

if __name__ == '__main__':
    # JWTs are obtained by IAP-protected applications whenever an
    # end-user makes a request.  We've set up an app that echoes back
    # the JWT in order to expose it to this test.  Thus, this test
    # exercises both make_iap_request and validate_jwt.
    res = make_iap_request(
        'https://{}/'.format(REFLECT_SERVICE_HOSTNAME),
        IAP_CLIENT_ID)
    print res
