import dataclasses
from pdb import set_trace as T

import gymnasium

from pokegym import Environment as env_creator

import pufferlib.emulation


def make_env(headless: bool = True, state_path=None, save_video: bool = False):
    '''Pokemon Red'''
    env = env_creator(dataclasses, headless=headless, state_path=state_path, save_video=save_video)
    return pufferlib.emulation.GymnasiumPufferEnv(env=env,
        postprocessor_cls=pufferlib.emulation.BasicPostprocessor)
