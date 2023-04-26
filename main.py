import os
import re
import openai
import spotipy
import webbrowser
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from dotenv import load_dotenv
from typing import Dict, Union, List, Tuple


# load in credentials from .env file
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

PROMPT_OUTPUT_FILE = './promptres.txt'
SPOTIFY_REDIRECT_URL = 'http://localhost:8000/callback'


class TextModelConfig:
    def __init__(self, model_name: str = 'text-davinci-003', temperature: float = 0.87, max_tokens: int = 350, 
                 top_p: int = 1,frequency_penalty: float = 0.0, presence_penalty: float = 0.0, stop: List[str] = []):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.stop = stop


class GeneratorConfig:
    def __init__(self, openai_key: str, spotify_client_id: str, spotify_client_secret: str,
                 spotify_redirect_url: str, output_file: str = ''):
        self.openai_key = openai_key
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.spotify_redirect_url = spotify_redirect_url
        self.output_file = output_file # optional (used to save on OpenAI API credits when testing)


class NewPlaylistParams:
    def __init__(self, playlist_name: str, playlist_seed: str, num_songs: int = 15,
                 public: bool = True, collaborative: bool = False):
        self.playlist_name = playlist_name
        self.playlist_seed = playlist_seed
        self.num_songs = num_songs
        self.public = public
        self.collaborative = collaborative


class PlaylistGPTGenerator:
    def __init__(self, config: GeneratorConfig, model_config: TextModelConfig):
        self.config = config
        self.model_config = model_config

    def read_saved_prompt_output(self) -> List[str]:
        try:
            with open(self.config.output_file, 'r') as file:
                return file.readlines()
        except FileNotFoundError:
            print(f"Error: File {self.config.output_file} not found.")
            return []
        except Exception as e:
            print(f"Error reading file {self.config.output_file}: {e}")
            return []
    
    def save_prompt_output(self, prompt_output: str) -> None:
        try:
            with open(self.config.output_file, 'a') as file:
                file.write(prompt_output)
        except Exception as e:
            print(f"Error saving file {self.config.output_file}: {e}")

    def generate_prompt(self, num_songs: int, playlist_seed: str) -> str:
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
            """.format(num_songs, playlist_seed.capitalize())

    def call_openai_api(self, num_songs: int, playlist_seed: str) -> str:
        try:
            openai.api_key = self.config.openai_key
            prompt = self.generate_prompt(num_songs=num_songs, playlist_seed=playlist_seed)
            stop = [str(num_songs) + "."] if not self.model_config.stop else self.model_config.stop

            response = openai.Completion.create(
                model=self.model_config.model_name,
                prompt=prompt,
                temperature=self.model_config.temperature,
                max_tokens=self.model_config.max_tokens,
                top_p=self.model_config.top_p,
                frequency_penalty=self.model_config.frequency_penalty,
                presence_penalty=self.model_config.presence_penalty,
                stop=stop
            )
            return response.choices[0].text
        except openai.error.OpenAIError as e:
            print(f"Error calling OpenAI API: {e}")
            return ''
        except Exception as e:
            print(f"Unexpected error calling OpenAI API: {e}")
            return ''
    
    def format_output(self, song_list_raw: List[str]) -> Dict[str, Union[Dict, None]]:
        filtered_lines = [line.strip()[line.find('.') + 1:].strip() for line in song_list_raw if line.strip()]
        track_data = {}
        for idx, line in enumerate(filtered_lines):
            track, artist = line.split(',')
            track_data[f'Song #{idx + 1}'] = {'track': track, 'artist': artist}
        return track_data
    
    def get_playlist_songs(self, num_songs: int, playlist_seed: str) -> Dict[str, Union[Dict, None]]:
        song_list_raw = []

        if os.path.isfile(self.config.output_file):
            song_list_raw = self.read_saved_prompt_output()
        elif self.config.api_key:
            api_response = self.call_openai_api(num_songs, playlist_seed)
            if api_response:
                self.save_prompt_output(api_response)
                song_list_raw = api_response.split('\n')
        else:
            print("Error: API key not provided.")

        return self.format_output(song_list_raw)

    def create_spotipy_instance(self, public: bool = False) -> spotipy.Spotify:
        scope = 'playlist-modify-public' if public else 'playlist-modify-private'
        return spotipy.Spotify(
            oauth_manager=SpotifyOAuth(
                client_id=self.config.spotify_client_id,
                client_secret=self.config.spotify_client_secret,
                redirect_uri=self.config.spotify_redirect_url,
                scope=scope
            )
        )

    def create_spotify_playlist(self, playlist_name: str, playlist_desc: str, track_data: Dict[str, Union[Dict, None]],
                                public: bool = False, collaborative: bool = False) -> str:
        spotipy_instance = None
        if (self.config.spotify_client_id and self.config.spotify_client_secret and self.config.spotify_redirect_url):
            spotipy_instance = self.create_spotipy_instance(public=public)
            if spotipy_instance:
                song_ids = []
                for entry in track_data.values():
                    query = 'artist:{} track:{}'.format(entry['artist'], entry['track'])
                    song_search_result = spotipy_instance.search(q=query, type='track', limit=1)
                    if song_search_result['tracks']['items']:
                        song_ids.append(song_search_result['tracks']['items'][0]['id'])


                # create the new playlist for the current user, with the songs gathered
                user_id = spotipy_instance.me()['id']
                playlist = spotipy_instance.user_playlist_create(
                    user=user_id,
                    name=playlist_name,
                    description=playlist_desc,
                    public=public,
                    collaborative=collaborative
                )

                # add the songs
                spotipy_instance.playlist_add_items(
                    playlist_id=playlist['id'],
                    items=song_ids
                )

                # open the newly created playlist
                playlist_url = playlist['external_urls']['spotify']
                return playlist_url
        else:
            print("Error: Missing Spotify authenication information")
            return ''
    
    def generate_new_gpt_playlist(self, new_playlist_params: NewPlaylistParams) -> str:
        if (new_playlist_params.num_songs and new_playlist_params.playlist_seed and new_playlist_params.playlist_name):
            playlist_songs = self.get_playlist_songs(num_songs=new_playlist_params.num_songs,
                                                    playlist_seed=new_playlist_params.playlist_seed)
            if playlist_songs:
                return self.create_spotify_playlist(
                    playlist_name=new_playlist_params.playlist_name,
                    playlist_desc="Generated playlist of {} songs with prompt: {}".format(new_playlist_params.num_songs, 
                                                                                          new_playlist_params.playlist_seed),
                    track_data=playlist_songs,
                    public=new_playlist_params.public,
                    collaborative=new_playlist_params.collaborative
                )
            print("Error: generated playlist of songs is empty")
            return ''
        else:
            print("Error: missing new playlist params")
            return ''