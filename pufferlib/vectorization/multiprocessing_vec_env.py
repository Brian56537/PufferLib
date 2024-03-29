from pdb import set_trace as T
import numpy as np
import psutil
import time

import selectors
from multiprocessing import Process, Queue, Manager, Pipe, Array
from queue import Empty

from pufferlib import namespace
from pufferlib.vectorization.vec_env import (
    RESET,
    calc_scale_params,
    setup,
    single_observation_space,
    _single_observation_space,
    single_action_space,
    single_action_space,
    structured_observation_space,
    flat_observation_space,
    unpack_batched_obs,
    reset_precheck,
    recv_precheck,
    send_precheck,
    aggregate_recvs,
    split_actions,
    aggregate_profiles,
)


def init(self: object = None,
        env_creator: callable = None,
        env_args: list = [],
        env_kwargs: dict = {},
        num_envs: int = 1,
        envs_per_worker: int = 1,
        envs_per_batch: int = None,
        env_pool: bool = False,
        ) -> None:
    driver_env, multi_env_cls, agents_per_env = setup(
        env_creator, env_args, env_kwargs)
    num_workers, workers_per_batch, envs_per_batch, agents_per_batch, agents_per_worker = calc_scale_params(
        num_envs, envs_per_batch, envs_per_worker, agents_per_env)

    agents_per_worker = agents_per_env * envs_per_worker
    observation_size = int(np.prod(_single_observation_space(driver_env).shape))
    observation_dtype = _single_observation_space(driver_env).dtype

    # Shared memory for obs, rewards, terminals, truncateds
    shared_mem = [
        Array('d', agents_per_worker*(3+observation_size))
        for _ in range(num_workers)
    ]
    main_send_pipes, work_recv_pipes = zip(*[Pipe() for _ in range(num_workers)])
    work_send_pipes, main_recv_pipes = zip(*[Pipe() for _ in range(num_workers)])
    
    num_cores = psutil.cpu_count()
    #curr_process = psutil.Process()
    #curr_process.cpu_affinity([num_cores-1])
    processes = [Process(
        target=_worker_process,
        args=(multi_env_cls, env_creator, env_args, env_kwargs,
              agents_per_env, envs_per_worker,
              i%(num_cores-1), shared_mem[i],
              work_send_pipes[i], work_recv_pipes[i])
        )
        for i in range(num_workers)]

    for p in processes:
        p.start()

    # Register all receive pipes with the selector
    sel = selectors.DefaultSelector()
    for pipe in main_recv_pipes:
        sel.register(pipe, selectors.EVENT_READ)

    return namespace(self,
        processes = processes,
        sel = sel,
        observation_size = observation_size,
        observation_dtype = observation_dtype,
        shared_mem = shared_mem,
        send_pipes = main_send_pipes,
        recv_pipes = main_recv_pipes,
        driver_env = driver_env,
        num_envs = num_envs,
        num_workers = num_workers,
        workers_per_batch = workers_per_batch,
        envs_per_batch = envs_per_batch,
        envs_per_worker = envs_per_worker,
        agents_per_batch = agents_per_batch,
        agents_per_worker = agents_per_worker,
        agents_per_env = agents_per_env,
        async_handles = None,
        flag = RESET,
        prev_env_id = [],
        env_pool = env_pool,
    )

def _unpack_shared_mem(shared_mem, n):
    np_buf = np.frombuffer(shared_mem.get_obj(), dtype=float)
    obs_arr = np_buf[:-3*n]
    rewards_arr = np_buf[-3*n:-2*n]
    terminals_arr = np_buf[-2*n:-n]
    truncated_arr = np_buf[-n:]

    return obs_arr, rewards_arr, terminals_arr, truncated_arr

def _worker_process(multi_env_cls, env_creator, env_args, env_kwargs,
        agents_per_env, envs_per_worker,
        worker_idx, shared_mem, send_pipe, recv_pipe):

    # I don't know if this helps. Sometimes it does, sometimes not.
    # Need to run more comprehensive tests
    #curr_process = psutil.Process()
    #curr_process.cpu_affinity([worker_idx])

    envs = multi_env_cls(env_creator, env_args, env_kwargs, n=envs_per_worker)
    obs_arr, rewards_arr, terminals_arr, truncated_arr = _unpack_shared_mem(
        shared_mem, agents_per_env * envs_per_worker)

    while True:
        request, args, kwargs = recv_pipe.recv()
        func = getattr(envs, request)
        response = func(*args, **kwargs)
        info = {}

        # TODO: Handle put/get
        if request in 'step reset'.split():
            obs, reward, done, truncated, info = response

            # TESTED: There is no overhead associated with 4 assignments to shared memory
            # vs. 4 assigns to an intermediate numpy array and then 1 assign to shared memory
            obs_arr[:] = obs.ravel()
            rewards_arr[:] = reward.ravel()
            terminals_arr[:] = done.ravel()
            truncated_arr[:] = truncated.ravel()

        send_pipe.send(info)

def recv(state):
    recv_precheck(state)

    recvs = []
    next_env_id = []
    if state.env_pool:
        while len(recvs) < state.workers_per_batch:
            for key, _ in state.sel.select(timeout=None):
                response_pipe = key.fileobj
                env_id = state.recv_pipes.index(response_pipe)

                if response_pipe.poll():  # Check if data is available
                    info = response_pipe.recv()
                    o, r, d, t = _unpack_shared_mem(
                        state.shared_mem[env_id], state.agents_per_env * state.envs_per_worker)
                    o = o.reshape(
                        state.agents_per_env*state.envs_per_worker,
                        state.observation_size).astype(state.observation_dtype)

                    recvs.append((o, r, d, t, info, env_id))
                    next_env_id.append(env_id)

                if len(recvs) == state.workers_per_batch:
                    break
    else:
        for env_id in range(state.workers_per_batch):
            response_pipe = state.recv_pipes[env_id]
            info = response_pipe.recv()
            o, r, d, t = _unpack_shared_mem(
                state.shared_mem[env_id], state.agents_per_env * state.envs_per_worker)
            o = o.reshape(
                    state.agents_per_env*state.envs_per_worker,
                    state.observation_size).astype(state.observation_dtype)

            recvs.append((o, r, d, t, info, env_id))
            next_env_id.append(env_id)
 
    state.prev_env_id = next_env_id
    return aggregate_recvs(state, recvs)

def send(state, actions):
    send_precheck(state)
    actions = split_actions(state, actions)
    assert len(actions) == state.workers_per_batch
    for i, atns in zip(state.prev_env_id, actions):
        state.send_pipes[i].send(("step", [atns], {}))

def async_reset(state, seed=None):
    reset_precheck(state)
    if seed is None:
        for pipe in state.send_pipes:
            pipe.send(("reset", [], {}))
    else:
        for idx, pipe in enumerate(state.send_pipes):
            pipe.send(("reset", [], {"seed": seed+idx}))

def reset(state, seed=None):
    async_reset(state)
    obs, _, _, _, info, env_id, mask = recv(state)
    return obs, info, env_id, mask

def step(state, actions):
    send(state, actions)
    return recv(state)

def profile(state):
    # TODO: Update this
    for queue in state.request_queues:
        queue.put(("profile", [], {}))

    return aggregate_profiles([queue.get() for queue in state.response_queues])

def put(state, *args, **kwargs):
    # TODO: Update this
    for queue in state.request_queues:
        queue.put(("put", args, kwargs))

def get(state, *args, **kwargs):
    # TODO: Update this
    for queue in state.request_queues:
        queue.put(("get", args, kwargs))

    idx = -1
    recvs = []
    while len(recvs) < state.workers_per_batch // state.envs_per_worker:
        idx = (idx + 1) % state.num_workers
        queue = state.response_queues[idx]

        if queue.empty():
            continue

        response = queue.get()
        if response is not None:
            recvs.append(response)

    return recvs


def close(state):
    for pipe in state.send_pipes:
        pipe.send(("close", [], {}))

    for p in state.processes:
        p.terminate()

    for p in state.processes:
        p.join()
