import os
import re
import openai
import spotipy
import webbrowser
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from dotenv import load_dotenv


# load in credentials from .env file
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

PROMPT_OUTPUT_FILE = './promptres.txt'


def get_playlist_songs(num_songs, playlist_spec):
    # call openai API
    openai.api_key = OPENAI_KEY

    def generate_prompt(num_songs, playlist_spec):
        return """Please generate a playlist of songs.
    For your response, please ONLY respond with the list,
    formatted as a comma-separated pair of the song title and the artist
    and with each entry delimited by a new line.Do not say anything else but the list please.

    Playlist: 2 songs with the artist Peach Pit
    List:
    1. Brian's Party,Peach Pit
    2. Sweet F.A.,Peach Pit

    Playlist: 5 songs with instrumental deep, ambient, and somber tones for deep focusing
    List:
    1. Weightless,Marconi Union
    2. November,Max Richter
    3. Divenire,Ludovico Einaudi
    4. Into Dust,Mazzy Star
    5. Your Hand in Mine,Explosions in the Sky

    Playlist: {} songs with {}
    List:
        """.format(num_songs, playlist_spec.capitalize())

    # make the actual API call
    model_response = openai.Completion.create(
        model="text-davinci-003",
        prompt=generate_prompt(num_songs=num_songs, playlist_spec=playlist_spec),
        temperature=0.87,
        max_tokens=350,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=[str(num_songs) + "."]
    ).choices[0].text

    # save prompt result to file if it doesn't exist (to save on OpenAI API credits)
    with open(PROMPT_OUTPUT_FILE, 'a') as saved_prompt_res_file:
        saved_prompt_res_file.write(model_response)

    return model_response.split('\n')


def get_playlist_songs_raw(num_songs, playlist_spec):
    # return previous list if it exists (to save on OpenAI API credits)
    if os.path.isfile(PROMPT_OUTPUT_FILE):
        with open(PROMPT_OUTPUT_FILE, 'r') as saved_prompt_res_file:
            return saved_prompt_res_file.readlines()
    return get_playlist_songs(num_songs=num_songs, playlist_spec=playlist_spec)
    

def test_basic():
    # get output from GPT
    get_playlist_songs(20, "high energy old school hip-hop with heavy production")


# parse the results
playlist_songs_raw = get_playlist_songs_raw(20, "high energy old school hip-hop with heavy production")
filtered_lines = [re.sub(r'\n', '', re.sub(r'^\d+\. ', '', s)) for s in playlist_songs_raw if s and not s.isspace()]

playlist_dictionary = {}
for x in range(0, len(filtered_lines)):
    (track, artist) = tuple(filtered_lines[x].split(','))
    playlist_dictionary['Song #{}'.format(x + 1)] = {
        'track': track,
        'artist': artist
    }

# call the spotify API
oauth_manager = SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET,
                             redirect_uri='http://localhost:8000/callback', scope='playlist-modify-private')
spotify = spotipy.Spotify(oauth_manager=oauth_manager)

song_ids = []
for entry in playlist_dictionary.values():
    query = 'artist:{} track:{}'.format(entry['artist'], entry['track'])
    song_search_result = spotify.search(q=query, type='track', limit=1)
    if song_search_result['tracks']['items']:
        song_ids.append(song_search_result['tracks']['items'][0]['id'])


# create the new playlist for the current user, with the songs gathered
playlist_name = "My New PlaylistGPT Playlist"
playlist_desc = "{} songs with prompt: {}".format(20, "high energy old school hip-hop with heavy production")
user_id = spotify.me()['id']

playlist = spotify.user_playlist_create(
    user=user_id,
    name=playlist_name,
    description=playlist_desc,
    public=False,
    collaborative=False
)

# add the songs
spotify.playlist_add_items(
    playlist_id=playlist['id'],
    items=song_ids
)

# open the newly created playlist
playlist_url = playlist['external_urls']['spotify']
webbrowser.open(playlist_url)