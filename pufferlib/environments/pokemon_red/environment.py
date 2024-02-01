from pdb import set_trace as T

import gymnasium
import functools

from pokegym import Environment
import pufferlib.emulation
from pufferlib.environments.pokemon_red.stream_wrapper import StreamWrapper



def env_creator(name='pokemon_red'):
    return functools.partial(make, name)

def make(name, headless: bool = True, state_path=None):
    '''Pokemon Red'''
    env = Environment(headless=headless, state_path=state_path)
    env = StreamWrapper(
            env, 
            stream_metadata = { # stream_metadata is optional
                "user": "Leanke", # your username
                "color": "#006A4E", # color for your text :)
                "extra": "", # any extra text you put here will be displayed
            }
        )
    return pufferlib.emulation.GymnasiumPufferEnv(env=env,
        postprocessor_cls=pufferlib.emulation.BasicPostprocessor)
