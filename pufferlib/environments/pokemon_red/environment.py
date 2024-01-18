from pdb import set_trace as T

import gymnasium
import functools

from pokegym import Environment

import pufferlib.emulation


def env_creator(name='pokemon_red'):
    return functools.partial(make, name)

def make(name, headless: bool = True, state_path=None, save_video: bool = False):
    '''Pokemon Red'''
    env = Environment(headless=headless, state_path=state_path, save_video=save_video)
    return pufferlib.emulation.GymnasiumPufferEnv(env=env,
        postprocessor_cls=pufferlib.emulation.BasicPostprocessor)
 # --env-kwargs.save-video