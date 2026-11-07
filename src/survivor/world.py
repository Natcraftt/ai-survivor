"""Le monde : l'état de la partie et les règles pour passer d'un tour au suivant.

Aucune dépendance à une fenêtre : le monde ne sait pas comment il est affiché.
"""


class World:
    NB_MAX_TOUR = 150

    def __init__(self):
        self.reset()

    def reset(self):
        """Remet le monde à son état de départ."""
        self.nb_tours = 0

    def step(self, action):
        """Fait avancer le monde d'un tour. L'action est ignorée pour l'instant."""
        if self.is_done():
            raise RuntimeError("La partie est finie : appelle reset() avant de rejouer.")
        self.nb_tours += 1

    def is_done(self):
        return self.nb_tours >= self.NB_MAX_TOUR

    def to_dict(self):
        return {"nb_tours": self.nb_tours}

    def from_dict(self, data):
        self.nb_tours = data["nb_tours"]