from playlistgpt import *
from fastapi import FastAPI
from pydantic import BaseModel

# load in credentials from .env file
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

PROMPT_OUTPUT_FILE = './promptres.txt'
SPOTIFY_REDIRECT_URL = 'http://localhost:8000/callback'

app = FastAPI()

class PlaylistCreate(BaseModel):
    playlist_name: str
    playlist_seed: str
    num_songs: int
    public: bool
    collaborative: bool


@app.post("/create-playlist")
async def create_playlist(playlist_req: PlaylistCreate):
    # create text model config
    text_model_conf = TextModelConfig()

    # create generator config
    generator_conf = GeneratorConfig(
        openai_key=OPENAI_KEY,
        spotify_client_id=SPOTIFY_CLIENT_ID,
        spotify_client_secret=SPOTIFY_CLIENT_SECRET,
        spotify_redirect_url=SPOTIFY_REDIRECT_URL,
        output_file=PROMPT_OUTPUT_FILE
    )

    # create playlist params
    playlist_params = NewPlaylistParams(
        playlist_name=playlist_req.playlist_name,
        playlist_seed=playlist_req.playlist_seed,
        num_songs=playlist_req.num_songs,
        public=playlist_req.public,
        collaborative=playlist_req.collaborative
    )

    generator = PlaylistGPTGenerator(
        config=generator_conf,
        model_config=text_model_conf
    )
    return generator.generate_new_gpt_playlist(new_playlist_params=playlist_params)