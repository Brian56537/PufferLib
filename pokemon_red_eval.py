# One-off demo for pokemon red because there isn't a clean way to put
# the custom map overlay logic into the clean_pufferl file and I want
# to keep that file as minimal as possible
from pathlib import Path
import numpy as np
import torch

def make_pokemon_red_overlay(bg, counts):
    nonzero = np.where(counts > 0, 1, 0)
    scaled = np.clip(counts, 0, 1000) / 1000.0

    # Convert counts to hue map
    hsv = np.zeros((*counts.shape, 3))
    hsv[..., 0] = 2*(1-scaled)/3
    hsv[..., 1] = nonzero
    hsv[..., 2] = nonzero

    # Convert the HSV image to RGB
    import matplotlib.colors as mcolors
    overlay = 255*mcolors.hsv_to_rgb(hsv)

    # Upscale to 16x16
    kernel = np.ones((16, 16, 1), dtype=np.uint8)
    overlay = np.kron(overlay, kernel).astype(np.uint8)
    mask = np.kron(nonzero, kernel[..., 0]).astype(np.uint8)
    mask = np.stack([mask, mask, mask], axis=-1).astype(bool)

    # Combine with background
    render = bg.copy().astype(np.int32)
    render[mask] = 0.2*render[mask] + 0.8*overlay[mask]
    render = np.clip(render, 0, 255).astype(np.uint8)
    return render

def rollout(env_creator, env_kwargs, agent_creator, agent_kwargs, model_path=None, device='cuda', verbose=True):
    env = env_creator(**env_kwargs)
    if model_path is None:
        agent = agent_creator(env, **agent_kwargs)
    else:
        agent = torch.load(model_path, map_location=device)

    terminal = truncated = True

    import cv2
    bg = cv2.imread('kanto_map_dsv.png')

    while True:
        if terminal or truncated:
            if verbose:
                print('---  Reset  ---')

            ob, info = env.reset()
            state = None
            step = 0
            return_val = 0

        ob = torch.tensor(ob).unsqueeze(0).to(device)
        with torch.no_grad():
            if hasattr(agent, 'lstm'):
                action, _, _, _, state = agent.get_action_and_value(ob, state)
            else:
                action, _, _, _ = agent.get_action_and_value(ob)

        ob, reward, terminal, truncated, _ = env.step(action[0].item())
        return_val += reward

        counts_map = env.env.counts_map
        if np.sum(counts_map) > 0 and step % 500 == 0:
            overlay = make_pokemon_red_overlay(bg, counts_map)
            cv2.imshow('Pokemon Red', overlay[1000:][::4, ::4])
            cv2.waitKey(1)

        if verbose:
            print(f'Step: {step} Reward: {reward:.4f} Return: {return_val:.2f}')

        if not env_kwargs['headless']:
            env.render()

        step += 1


def logger(pokemon_info, log_path):
    for pokemon in pokemon_info:
        for p in pokemon:
            env_id = p['env_id']
            log_file = Path(f"{env_id}").with_suffix('.txt')
            log_file_path = log_path / log_file
        with open(log_file_path, 'w') as log:
            for p in pokemon:
                if env_id and str(p['level']) != str(0):
                    log.write(f"============= {p['env_id']} =============\n")
                    log.write(f"Slot: {p['slot']}\n")
                    log.write(f"Name: {p['name']}\n")
                    log.write(f"Level: {p['level']}\n")
                    log.write(f"Moves: {', '.join(p['moves'])}\n")
                    log.write("\n============== Unique Items ==============\n")
                    unique_items = set(p['items']) if 'items' in p else set()
                    for item in sorted(unique_items):
                        log.write(f"{item}\n")
                        


        # upokemon = set()
        # umoves = set()
        # uitems = set()
        # count = 0
        # agg_file = Path(f"log").with_suffix('.txt')
        # agg_file_path = log_path / agg_file
        # upokemon.add(p['name'])
        # umoves.add(p['moves'])
        # uitems.add(p['items'])
        # if count >= 1:
        #     with open(agg_file_path, 'w') as agg:
        #         agg.write("============= Unique Pokemon =============\n")
        #         for po in sorted(upokemon):
        #             agg.write(f"{po}\n")
        #         agg.write("\n============== Unique Moves ==============\n")
        #         for m in sorted(umoves):
        #             agg.write(f"{m}\n")
        #         agg.write("\n============== Unique Items ==============\n")
        #         for i in sorted(uitems):
        #             agg.write(f"{i}\n")

# def logger2(values, log_path):
#     for pokemon_session in values:
#         for pokemon in pokemon_session:
#             log_file = Path(f"{pokemon['env_id']}").with_suffix('.txt')
#             log_file_path = log_path / log_file
#             with open(log_file_path, 'w') as log:

# def logger(values, log_path):
#     unique_pokemon = set()
#     unique_moves = set()
#     unique_items = set()
#     unique_env = set()
#     log_file = Path(f'log').with_suffix('.txt')
#     log_file_path = log_path / log_file
#     for pokemon_session in values:
#         for pokemon in pokemon_session:
#             unique_pokemon.add(pokemon['name'])
#             unique_moves.update(pokemon['moves'])
#             unique_items.update(pokemon['items'])
#     with open(log_file_path, 'w') as log:
#         log.write("============= Unique Pokemon =============\n")
#         for upokemon in sorted(unique_pokemon):
#             log.write(f"{upokemon}\n")
#         log.write("\n============== Unique Moves ==============\n")
#         for move in sorted(unique_moves):
#             log.write(f"{move}\n")
#         log.write("\n============== Unique Items ==============\n")
#         for item in sorted(unique_items):
#             log.write(f"{item}\n")
#         log.write("\n================== Log Entries ==================\n")
#         for pokemon_session in values:
#             env_id = (p for p in pokemon_session if p['env_id'] not in unique_env)
#             log.write(f"=============={pokemon['env_id']}==============\n")
#             for pokemon in pokemon_session:
#                 if env_id and str(pokemon['level']) != str(0):
#                     log.write(f"  Slot: {pokemon['slot']}\n")
#                     log.write(f"  Name: {pokemon['name']}\n")
#                     log.write(f"  Level: {pokemon['level']}\n")
#                     log.write(f"  Moves: {', '.join(pokemon['moves'])}\n")
#                     log.write("  \n")  # Add a newline between Pokémon
#                 unique_env.add(pokemon['env_id'])