import os
from requests_oauthlib import OAuth2Session
from urllib.parse import quote
import requests

# Dropbox app credentials (replace with your app's values)
DROPBOX_CLIENT_ID = 'sq0d8qtiwqjj4e9'
DROPBOX_CLIENT_SECRET = '9hxg9bxidahmbld'

# Temporary short-lived access token (from the Dropbox App Console)
SHORT_LIVED_ACCESS_TOKEN = "sl.u.AFhdH5S8ekPMSXzPsJ2l-Wx8dRx6iC4dbEngRBfLjd5px_3d8CWAqB1QBImHMXEKvjQCrxl-AdNP9mOtxPc7eiAkqF8qlYy02MJQ5sGerYe9-bigp9Vc6Dbi7CDl0V-ZAXXyoMJTM_ieG7twTmlBNZUO-MrYy8v9w1qBFCtRGEZjyuGxEpquHfpUxxx3bUoF_DDyRR-3JvU2YnxNEE3k2-RRni9Dd7zkGU6ewEfKKoHXCV-u-BoHnp2GKmTGrapJ0VBHYCHiCf_IHmG0BLOCE0GJBINNIFP3Q3UsiL03ZS8cHIzh1NUoLMkDzFgrFEC7umIRjabaoa9quGKSbTawjoX7ddvzRU1MnwURn4YHWGXlQBX1gjN5jEGyHCxXA-dozbXiUKpJlji47o6E7f-OlOx2sXrtXRwkAkaYFLat625iL6-YWb2u7jlq1btv1s6IPVrRMuMCN5V6G-ssBkz4i0QnDQqgpVnopBnEIorIeYS76Iatt7KjilLTZSWxcPhPqYqEjM-HmEOK8i215fKfNAwUGg9PznMNPUX8iaSe-5QBLBUL6H7jse41Hm0ruwBhY4mujsz9m-deLDESKnLUIPU7fKq6cMXaX0Hgv2s4EBSzSuqx7WwmVvQ4z0IdqWU4W2Pnd6kBqI8v995y-ycwF0BP2-4OCmqy7aW4gwMepEqXUEE5sJnTzZ1JT9tNqxLc6O3RsXLGd_auVdq2TlKa5a_wgI35ifhFDIeafbX74WlWBqNziBq6YLV4pkx03pZ3kTL0HIpQuWgqmLvt0Dszw9TnTKlsy-zfMGu-ypcAO5XEbMOQ0RSSfpu3FFl8rZU7Ab2PrVQZsP3sCVPFxeeHN8eGH_6jqvXA0NqJhl6lyysCdEfVUJMi0Oc7nS7ifKFYk-iMmJ1j2wlZQ7fzrJV7QdBS2uzjSyXWu4wWoFtqPYlrTFN_K8LIiTiSYiWH8pY0UDBiVLOIilNYFl3RtVnpwYlsh1Km4R2n9pVcoil4oGHg2-cg4erO9_TjDGtlTFyMYNuomJ0oZA-FmR6Es14yCScZwBPm4c8bmOak-nZ7_BBNWNIEmdGMtcrit2DYP_hVzea_kaBvV5Ewuyn9B1EZw1p1D8VWCzRe3fny3L1DbrZh_oYEj0phY2k4lmER2zi__74otLd2MwyltdOhojmaqnJfS3ztUP77di9ga-3Y-Wbwhd1ak0QK7t-6cGhyQbdZvHeemx-qG-FpBseYy35xJ77W_lgqOapklpfGdn4oCUJ41wtB1ayU2fgKTaKjOatUNm0Q5HkBpQ_qPhlgYhyc5445"

# Redirect URI (must be configured in your Dropbox App settings)
# Use "http://localhost" or a similar placeholder if you don't have a specific redirect URI
REDIRECT_URI = "http://localhost"

def get_refresh_token(client_id, client_secret, short_lived_token, redirect_uri):
    """
    Exchanges a short-lived access token for a refresh token.
    """
    
    # Encode the redirect URI
    encoded_redirect_uri = quote(redirect_uri)
    
    # Construct the authorization URL and print it
    authorization_base_url = 'https://www.dropbox.com/oauth2/authorize'
    authorization_url = f"{authorization_base_url}?client_id={client_id}&redirect_uri={encoded_redirect_uri}&response_type=code&token_access_type=offline"
    print(f"Please go to this URL and authorize the app:\n{authorization_url}\n")

    # Get the authorization code from user input after they authorize the app
    authorization_code = input("Paste the authorization code here: ")
    
    # Exchange the authorization code for an access token and refresh token
    token_url = 'https://api.dropboxapi.com/oauth2/token'
    data = {
        'code': authorization_code,
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    token_data = response.json()

    print("Refresh Token:", token_data['refresh_token'])
    return token_data['refresh_token']

# Run the function to get your refresh token
if __name__ == "__main__":
    get_refresh_token(DROPBOX_CLIENT_ID, DROPBOX_CLIENT_SECRET, SHORT_LIVED_ACCESS_TOKEN, REDIRECT_URI)