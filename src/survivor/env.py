"""Interface Gymnasium : la « prise » standard où les algorithmes d'apprentissage se branchent.

NOUVEAU (ticket 1.6). Gymnasium impose un vocabulaire commun :
  - reset()  -> (observation, info)                        : démarre une partie ;
  - step(a)  -> (observation, récompense, terminated, truncated, info) : joue un tour.
Grâce à lui, n'importe quel algorithme (Stable-Baselines3, etc.) peut jouer à notre jeu sans rien
connaître de notre moteur.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .actions import N_ACTIONS
from .perception import OBSERVATION_SIZE, observe
from .reward import compute_reward
from .world import World


class SurvivalEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config=None):
        super().__init__()
        self.world = World(config, seed=0)
        # Ce que l'agent peut faire : choisir un numéro d'action entre 0 et N_ACTIONS - 1.
        self.action_space = spaces.Discrete(N_ACTIONS)
        # Ce que l'agent reçoit : un vecteur de OBSERVATION_SIZE nombres entre -1 et 1.
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(OBSERVATION_SIZE,), dtype=np.float32
        )

    def reset(self, *, seed=None, options=None):
        # super().reset(seed=...) initialise self.np_random, le générateur aléatoire de l'environnement.
        # On en tire la graine du monde : même `seed` donné ici => même première partie ;
        # resets suivants sans graine => parties différentes mais reproductibles.
        super().reset(seed=seed)
        self.world.reset(int(self.np_random.integers(0, 2**31 - 1)))
        return observe(self.world), self._info()

    def step(self, action):
        self.world.step(int(action))
        # Gymnasium distingue deux façons de finir une partie :
        #  - terminated : la partie s'arrête « pour de vrai » (le joueur est mort) ;
        #  - truncated  : on coupe parce que la limite de tours est atteinte (le joueur a survécu).
        # La différence compte pour l'apprentissage : survivre jusqu'au bout n'est pas une fin « mauvaise ».
        terminated = self.world.dead
        truncated = (not terminated) and self.world.is_done()
        return (
            observe(self.world),
            compute_reward(self.world),
            terminated,
            truncated,
            self._info(),
        )

    def action_masks(self):
        """Masque des actions utiles, au format attendu par MaskablePPO (bibliothèque sb3-contrib)."""
        return np.array(self.world.action_mask(), dtype=bool)

    def _info(self):
        """Informations annexes, pour le suivi et le débogage (l'IA ne les reçoit pas)."""
        return {"hp": self.world.hp, "nb_tours": self.world.nb_tours, "seed": self.world.seed}