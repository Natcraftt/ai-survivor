"""Tests du ticket 1.4 : armes et medkit (ramassage, utilisation, effets).

Comment lire ces tests : chacun met en place une petite situation, joue UN tour, puis vérifie
ce qui a changé. Le joueur démarre toujours en (6, 6) au centre de la carte 12x12.
"""

import random

from survivor.actions import MOVES, Action
from survivor.world import World, WorldConfig, Zombie

ATTENDRE = Action.ATTENDRE


def monde(seed=0, **reglages):
    """Monde de test : aucun zombie, aucune apparition, aucun objet. On pose ce qu'il faut à la main.

    zombie_move_prob=0 par défaut : les zombies restent là où on les met (sauf s'ils attaquent).
    """
    base = {
        "n_zombies": 0, "spawn_prob": 0.0, "place_items": False, "zombie_move_prob": 0.0,
        "wall_density": 0.0, "random_start": False,  # arène vide, joueur au centre
    }
    base.update(reglages)
    return World(WorldConfig(**base), seed=seed)


def avec_arme(w, balles=4):
    """Donne une arme chargée au joueur (raccourci pour ne pas avoir à la ramasser)."""
    w.has_weapon = True
    w.ammo = balles


# ================================================================== les numéros d'actions
def test_les_actions_ont_les_numeros_attendus():
    # L'IA apprendra avec ces numéros : ils ne doivent jamais changer en silence.
    assert [a.value for a in (Action.HAUT, Action.DROITE, Action.BAS, Action.GAUCHE)] == [0, 1, 2, 3]
    assert Action.ATTENDRE == 4
    assert Action.ATTAQUER == 5
    assert Action.SOIGNER == 6


# ================================================================== objets posés sur la carte
def test_un_monde_neuf_a_une_arme_et_un_medkit_bien_places():
    for seed in range(30):
        w = World(seed=seed)
        assert w.weapon_pos is not None and w.medkit_pos is not None, seed
        cases = [w.weapon_pos, w.medkit_pos, w.player] + [(z.x, z.y) for z in w.zombies]
        assert len(set(cases)) == len(cases), seed  # aucune case partagée
        assert w.is_free(*w.weapon_pos) and w.is_free(*w.medkit_pos), seed  # jamais dans un mur


def test_le_joueur_commence_sans_arme_et_sans_medkit():
    w = World(seed=0)
    assert not w.has_weapon
    assert w.ammo == 0
    assert w.medkits == 0


def test_sans_place_items_la_carte_est_vide():
    w = monde()
    assert w.weapon_pos is None and w.medkit_pos is None


def test_une_carte_minuscule_ne_plante_pas():
    # Taille 3 : l'intérieur ne contient qu'une case, celle du joueur. Pas de place pour un objet.
    w = World(WorldConfig(size=3, n_zombies=0, spawn_prob=0.0), seed=0)
    assert w.weapon_pos is None and w.medkit_pos is None


def test_memes_graines_memes_objets_graines_differentes_objets_differents():
    assert World(seed=9).weapon_pos == World(seed=9).weapon_pos
    positions = {(World(seed=s).weapon_pos, World(seed=s).medkit_pos) for s in range(10)}
    assert len(positions) > 1


def test_add_wall_refuse_de_boucher_un_objet():
    w = monde()
    w.weapon_pos = (3, 3)
    w.medkit_pos = (4, 4)
    for x, y in [(3, 3), (4, 4)]:
        try:
            w.add_wall(x, y)
        except ValueError:
            pass
        else:
            raise AssertionError(f"add_wall({x}, {y}) aurait dû refuser")


# ================================================================== ramassage
def test_marcher_sur_l_arme_la_ramasse():
    w = monde()
    w.weapon_pos = (7, 6)  # juste à droite du joueur
    w.step(Action.DROITE)
    assert w.has_weapon
    assert w.ammo == w.config.weapon_ammo == 4
    assert w.weapon_pos is None  # l'objet a disparu de la carte


def test_marcher_sur_le_medkit_le_ramasse():
    w = monde()
    w.medkit_pos = (6, 7)  # juste en dessous du joueur
    w.step(Action.BAS)
    assert w.medkits == 1
    assert w.medkit_pos is None


def test_passer_a_cote_ne_ramasse_rien():
    w = monde()
    w.weapon_pos = (8, 6)  # deux cases à droite
    w.step(Action.DROITE)  # on n'arrive qu'en (7, 6)
    assert not w.has_weapon
    assert w.weapon_pos == (8, 6)


def test_on_ne_peut_pas_ramasser_deux_fois_le_meme_objet():
    w = monde()
    w.weapon_pos = (7, 6)
    w.step(Action.DROITE)  # ramassé : 4 balles
    w.step(Action.GAUCHE)
    w.step(Action.DROITE)  # on repasse sur la case : rien de nouveau
    assert w.ammo == 4


# ================================================================== attaque : tir
def test_un_tir_a_portee_tue_un_zombie_et_coute_une_balle():
    w = monde()
    avec_arme(w, balles=4)
    w.zombies.append(Zombie(9, 6))  # distance 3 = portée maximale
    w.step(Action.ATTAQUER)
    assert w.zombies == []  # un tir fait 2 dégâts, le zombie a 2 PV
    assert w.ammo == 3


def test_un_zombie_hors_de_portee_n_est_pas_touche_et_aucune_balle_n_est_perdue():
    w = monde()
    avec_arme(w, balles=4)
    w.zombies.append(Zombie(10, 6))  # distance 4 > portée 3
    w.step(Action.ATTAQUER)
    assert w.zombies[0].hp == 2
    assert w.ammo == 4


def test_attaquer_sans_zombie_ne_gaspille_pas_de_balle():
    w = monde()
    avec_arme(w, balles=4)
    w.step(Action.ATTAQUER)
    assert w.ammo == 4


def test_l_attaque_vise_le_zombie_le_plus_proche():
    w = monde()
    avec_arme(w)
    w.zombies.extend([Zombie(9, 6), Zombie(7, 6)])  # le second est collé au joueur
    w.step(Action.ATTAQUER)
    assert [(z.x, z.y) for z in w.zombies] == [(9, 6)]  # le proche est mort, le lointain reste


def test_la_derniere_balle_puis_plus_de_tir():
    w = monde()
    avec_arme(w, balles=1)
    w.zombies.append(Zombie(9, 6))
    w.step(Action.ATTAQUER)
    assert w.ammo == 0 and w.zombies == []
    w.zombies.append(Zombie(9, 6))
    w.step(Action.ATTAQUER)  # plus de balles : à distance 3, l'attaque rate
    assert w.zombies[0].hp == 2


# ================================================================== attaque : coup de poing
def test_sans_arme_on_frappe_a_mains_nues_un_zombie_adjacent():
    w = monde()
    w.zombies.append(Zombie(7, 6))
    w.step(Action.ATTAQUER)
    assert w.zombies[0].hp == 1  # 2 PV - 1 de poing
    w.step(Action.ATTAQUER)
    assert w.zombies == []  # le deuxième coup le tue


def test_sans_arme_on_ne_frappe_pas_a_distance_2():
    w = monde()
    w.zombies.append(Zombie(8, 6))
    w.step(Action.ATTAQUER)
    assert w.zombies[0].hp == 2


def test_arme_vide_on_frappe_au_poing_si_adjacent_et_on_rate_sinon():
    w = monde()
    avec_arme(w, balles=0)  # on a ramassé l'arme mais elle est vide
    w.zombies.append(Zombie(8, 6))  # distance 2
    w.step(Action.ATTAQUER)
    assert w.zombies[0].hp == 2  # rien
    w.zombies[0].x = 7  # le zombie se colle au joueur
    w.step(Action.ATTAQUER)
    assert w.zombies[0].hp == 1  # coup de poing


# ================================================================== l'ordre du tour
def test_un_zombie_tue_par_le_joueur_n_attaque_pas_ce_tour_la():
    w = monde()
    avec_arme(w)
    w.zombies.append(Zombie(7, 6))  # adjacent
    w.step(Action.ATTAQUER)  # le joueur agit AVANT les zombies : il tue celui-ci
    assert w.zombies == []
    assert w.hp == 5  # aucun dégât subi


def test_un_zombie_blesse_mais_vivant_attaque_quand_meme():
    w = monde()
    w.zombies.append(Zombie(7, 6))
    w.step(Action.ATTAQUER)  # poing : le zombie survit avec 1 PV
    assert w.hp == 4  # et il riposte


# ================================================================== soin
def test_un_medkit_rend_des_pv():
    w = monde()
    w.hp = 2
    w.medkits = 1
    w.step(Action.SOIGNER)
    assert w.hp == 5  # 2 + 3
    assert w.medkits == 0


def test_les_pv_ne_depassent_jamais_le_maximum():
    w = monde()
    w.hp = 4
    w.medkits = 1
    w.step(Action.SOIGNER)
    assert w.hp == 5  # 4 + 3 plafonné à 5
    assert w.medkits == 0  # le medkit est consommé : on était blessé


def test_a_pleine_sante_le_medkit_n_est_pas_consomme():
    w = monde()
    w.medkits = 1
    w.step(Action.SOIGNER)
    assert w.hp == 5
    assert w.medkits == 1


def test_sans_medkit_se_soigner_ne_fait_rien():
    w = monde()
    w.hp = 2
    w.step(Action.SOIGNER)
    assert w.hp == 2


def test_se_soigner_pres_d_un_zombie_le_soin_passe_avant_la_morsure():
    w = monde()
    w.hp = 2
    w.medkits = 1
    w.zombies.append(Zombie(7, 6))
    w.step(Action.SOIGNER)  # +3 (joueur d'abord), puis -1 (zombie ensuite)
    assert w.hp == 4


# ================================================================== sauvegarde et reset
def test_export_et_reconstruction_gardent_inventaire_et_objets():
    w = monde()
    w.weapon_pos = (3, 3)
    w.medkit_pos = (4, 4)
    w.medkits = 2
    avec_arme(w, balles=3)
    data = w.to_dict()

    copie = World()
    copie.from_dict(data)

    assert copie.to_dict() == data
    assert copie.weapon_pos == (3, 3) and copie.medkit_pos == (4, 4)  # tuples dans le monde
    assert data["weapon_pos"] == [3, 3]  # listes dans l'export
    assert (copie.ammo, copie.medkits, copie.has_weapon) == (3, 2, True)


def test_un_objet_ramasse_est_exporte_comme_absent():
    w = monde()
    w.weapon_pos = (7, 6)
    w.step(Action.DROITE)
    data = w.to_dict()
    assert data["weapon_pos"] is None
    copie = World()
    copie.from_dict(data)
    assert copie.weapon_pos is None


def test_reset_remet_inventaire_et_objets_a_zero():
    w = World(WorldConfig(n_zombies=0, spawn_prob=0.0), seed=2)
    avec_arme(w, balles=3)
    w.medkits = 2
    w.weapon_pos = w.medkit_pos = None
    w.reset()
    assert (w.has_weapon, w.ammo, w.medkits) == (False, 0, 0)
    assert w.weapon_pos is not None and w.medkit_pos is not None


# ================================================================== test d'ensemble
def test_invariants_sur_des_parties_aleatoires_avec_toutes_les_actions():
    # 100 parties jouées au hasard avec les 7 actions. À CHAQUE tour, des règles qui ne doivent
    # jamais être violées, quoi qu'il arrive.
    for seed in range(100):
        w = World(seed=seed)
        hasard = random.Random(seed)
        while not w.is_done():
            w.step(hasard.choice(list(Action)))
            assert 0 <= w.hp <= w.config.max_hp
            assert 0 <= w.ammo <= w.config.weapon_ammo  # une seule arme : 4 balles au maximum
            assert w.medkits in (0, 1)  # un seul medkit sur la carte
            assert all(z.hp > 0 for z in w.zombies)  # un zombie à 0 PV doit avoir disparu
            for objet in (w.weapon_pos, w.medkit_pos):
                assert objet is None or w.is_free(*objet)
            assert w.player not in [(z.x, z.y) for z in w.zombies]