import logging
import numpy as np
import torch
from torch import Tensor
from torch.utils.data import DataLoader
from torch.optim import Optimizer

from .data.transition import Transition, convert_to_transitions
from .data.replay_buffer import ReplayBuffer
from .env import Env
from .agent import Agent

def train(
        env: Env,
        agent: Agent,
        optimizer: Optimizer,
        n_epochs: int,
        replay_buffer: ReplayBuffer,
        max_n_timesteps_per_episode: int,
        warm_start_duration: int,
        batch_size: int,
        n_epochs_for_updating_agent: int,
        epsilon: float
    ):
        
    for epoch in range(n_epochs):
        
        logging.info(f"PPO epoch: {epoch + 1}")
        avg_episode_rewards = []
        
        # Collect transitions
        collect_transitions(
            replay_buffer=replay_buffer,
            env=env,
            agent=agent,
            max_n_timesteps_per_episode=max_n_timesteps_per_episode,
            warm_start_duration=warm_start_duration
        )
        
        rewards = []
        for transition in replay_buffer:
            rewards.append(transition.reward)
        avg_episode_reward = np.mean(rewards)
        avg_episode_rewards.append(avg_episode_reward)
        logging.info(f"average episode rewards: {avg_episode_reward}")
        
        # Create a data loader
        replay_buffer_loader = DataLoader(
            replay_buffer,
            batch_size=batch_size
        )
        
        # Train the actor and critic   
        update_agent(
            agent=agent,
            optimizer=optimizer,
            replay_buffer_loader=replay_buffer_loader,
            n_epochs=n_epochs_for_updating_agent,
            epsilon=epsilon
        )
        
        # Clear replay buffer
        replay_buffer.clear()

def collect_transitions(
        replay_buffer: ReplayBuffer,
        env: Env,
        agent: Agent,
        max_n_timesteps_per_episode: int,
        warm_start_duration: int
    ) -> None:
        
    while len(replay_buffer) < replay_buffer.capacity:
        
        # Collect transitions by interacting with the env
        transitions = play_one_episode(
            env=env,
            agent=agent,
            max_n_timesteps_per_episode=max_n_timesteps_per_episode,
            warm_start_duration=warm_start_duration
        )
        
        # Add to the buffer
        replay_buffer.extend(transitions)

def play_one_episode(
        env: Env,
        agent: Agent,
        max_n_timesteps_per_episode: int,
        warm_start_duration: int
    ) -> list[Transition]:
    
    states = []
    actions = []
    rewards = []
    log_probs = []

    state = env.reset()
    is_done = False
    
    for t in range(max_n_timesteps_per_episode):
        
        # Select an action
        state = torch.tensor(state, dtype=torch.float)
        action = agent.select_action(state)
        action = action.detach().numpy()
        
        # Compute the log-probability of the action taken
        log_prob = agent.log_prob()
        log_prob = log_prob.detach().item()
        
        # Interact with the env
        next_state, reward = env.step(action)
        
        states.append(state)
        actions.append(action)
        rewards.append(reward)
        log_probs.append(log_prob)
        
        # Step to the next state
        state = next_state
        
    # Compute baselines using moving average technique
    baselines = ema(np.array(rewards), period=warm_start_duration + 1)
        
    # Drop the data in the warm start
    states = states[warm_start_duration:]
    actions = actions[warm_start_duration:]
    rewards = rewards[warm_start_duration:]
    log_probs = log_probs[warm_start_duration:]
    
    # Compute advantages
    advantages = rewards - baselines
    
    transition_with_fields_as_list = Transition(
        state=states,
        action=actions,
        reward=rewards,
        advantage=advantages,
        log_prob=log_probs
    )
    
    # Convert to list of transitions
    transitions = convert_to_transitions(transition_with_fields_as_list)
    
    return transitions

def update_agent(
        agent: Agent,
        optimizer: Optimizer,
        replay_buffer_loader: DataLoader,
        n_epochs: int,
        epsilon: float = 0.2
    ):
    
    for _ in range(n_epochs):
        transition: Transition
        for transition in replay_buffer_loader:
            
            # Compute PPO loss
            loss = ppo_loss(
                curr_log_prob=agent.log_prob(
                    transition.action,
                    transition.state
                ),
                old_log_prob=transition.log_prob,
                advantage=transition.advantage,
                epsilon=epsilon
            )
            
            # Update the agent
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

def ppo_loss(
        *,
        curr_log_prob: Tensor,
        old_log_prob: Tensor,
        advantage: Tensor,
        epsilon: float = 0.2
    ) -> Tensor:
    
    ratio = torch.exp(curr_log_prob - old_log_prob)
    
    surr1 = ratio * advantage
    surr2 = torch.clip(
        ratio,
        1 - epsilon,
        1 + epsilon
    ) * advantage
    
    loss = -torch.min(surr1, surr2).mean()
    
    return loss

def sma(x: np.ndarray, period: int = 5) -> np.ndarray:
    """Simple Moving Average. 
    Compute the simple moving agverage of the input time series. 

    Parameters
    ----------
    x : np.ndarray
        _description_
    period : int, optional
        _description_, by default 5

    Returns
    -------
    np.ndarray
        _description_
    """
    
    assert len(x) >= period,\
        "the length of the array must be at least the length of the period"
    
    sma = []
    for t in range(period - 1, len(x)):
        sma.append(x[t-period+1:t].mean(axis=0))

    return np.array(sma)

def ema(
        x: np.ndarray, 
        period: int = 5,
        alpha: float = 0.2
    ) -> np.ndarray:
    """Exponential Moving Average. 
    Compute the exponential moving agverage of the input time series. 


    Parameters
    ----------
    x : np.ndarray
        _description_
    period : int, optional
        _description_, by default 5
    alpha : float, optional
        _description_, by default 0.2

    Returns
    -------
    np.ndarray
        _description_
    """
    
    assert len(x) >= period,\
        "the length of the array must be at least the length of the period"
    
    ema = []
    ema.append(x[:period].mean(axis=0))
    for i, t in enumerate(range(period, len(x))):
        ema.append(
            x[t] * alpha + ema[i] * (1 - alpha)
        )

    return np.array(ema)