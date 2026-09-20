from __future__ import annotations

from dataclasses import dataclass

from app.game.models import Element, Rarity, rarity_from_power


RANKER_2026_SOURCE = (
    "Ranker — The Most Attractive Anime Girls Of All Time "
    "(snapshot 2026-07-15)"
)
ANIME_CORNER_2025_SOURCE = (
    "Anime Corner — Best Female Character of the Year Ranking 2025 "
    "(published 2026-03-05)"
)


@dataclass(frozen=True, slots=True)
class WaifuDefinition:
    id: str
    name: str
    anime: str
    power_score: int
    element: Element
    ranker_rank: int | None = None
    recent_rank: int | None = None
    popularity_source: str = ""

    @property
    def rarity(self) -> Rarity:
        return rarity_from_power(self.power_score)

    @property
    def popularity_score(self) -> int:
        rank = self.ranker_rank or self.recent_rank
        if rank is None:
            return 40
        # Normalized source-relative score, deliberately not presented as
        # an objective popularity percentage.
        return max(25, round(100 - (rank - 1) * 1.5))


def _ranker(
    id: str,
    name: str,
    anime: str,
    rank: int,
    power_score: int,
    element: Element,
) -> WaifuDefinition:
    return WaifuDefinition(
        id=id,
        name=name,
        anime=anime,
        ranker_rank=rank,
        power_score=power_score,
        element=element,
        popularity_source=RANKER_2026_SOURCE,
    )


def _recent(
    id: str,
    name: str,
    anime: str,
    rank: int,
    power_score: int,
    element: Element,
) -> WaifuDefinition:
    return WaifuDefinition(
        id=id,
        name=name,
        anime=anime,
        recent_rank=rank,
        power_score=power_score,
        element=element,
        popularity_source=ANIME_CORNER_2025_SOURCE,
    )


RANKED_WAIFUS: tuple[WaifuDefinition, ...] = (
    _ranker("alisa-kujo", "Alisa Mikhailovna Kujo", "Alya Sometimes Hides Her Feelings in Russian", 1, 42, Element.ICE),
    _ranker("yor-forger", "Yor Forger", "SPY x FAMILY", 2, 86, Element.DARK),
    _ranker("rias-gremory", "Rias Gremory", "High School DxD", 3, 92, Element.DARK),
    _ranker("esdeath", "Esdeath", "Akame ga Kill!", 4, 98, Element.ICE),
    _ranker("akeno-himejima", "Akeno Himejima", "High School DxD", 5, 91, Element.LIGHTNING),
    _ranker("nami", "Nami", "One Piece", 6, 76, Element.LIGHTNING),
    _ranker("kuroka", "Kuroka", "High School DxD", 7, 90, Element.DARK),
    _ranker("aki-nijou", "Aki Nijou", "Maken-Ki!", 8, 58, Element.FIRE),
    _ranker("albedo", "Albedo", "Overlord", 9, 93, Element.DARK),
    _ranker("asuna-yuuki", "Asuna", "Sword Art Online", 10, 86, Element.LIGHT),
    _ranker("chizuru-mizuhara", "Chizuru Mizuhara", "Rent-a-Girlfriend", 11, 40, Element.NEUTRAL),
    _ranker("makima", "Makima", "Chainsaw Man", 12, 96, Element.DARK),
    _ranker("nico-robin", "Nico Robin", "One Piece", 13, 79, Element.EARTH),
    _ranker("yoruichi-shihoin", "Yoruichi Shihoin", "Bleach", 14, 91, Element.LIGHTNING),
    _ranker("violet-evergarden", "Violet Evergarden", "Violet Evergarden", 15, 48, Element.LIGHT),
    _ranker("erza-scarlet", "Erza Scarlet", "Fairy Tail", 16, 89, Element.EARTH),
    _ranker("elizabeth-liones", "Elizabeth Liones", "The Seven Deadly Sins", 17, 78, Element.LIGHT),
    _ranker("yumeko-jabami", "Yumeko Jabami", "Kakegurui", 18, 38, Element.MIND),
    _ranker("hinata-hyuga", "Hinata Hyuga", "Naruto", 19, 76, Element.LIGHT),
    _ranker("raphtalia", "Raphtalia", "The Rising of the Shield Hero", 20, 73, Element.EARTH),
    _ranker("tsunade", "Tsunade", "Naruto", 21, 93, Element.EARTH),
    _ranker("power", "Power", "Chainsaw Man", 22, 88, Element.DARK),
    _ranker("celistia-ralgris", "Celistia Ralgris", "Undefeated Bahamut Chronicle", 23, 67, Element.LIGHT,
    ),
    _ranker("akame", "Akame", "Akame ga Kill!", 24, 91, Element.DARK),
    _ranker("ai-hoshino", "Ai Hoshino", "Oshi no Ko", 25, 45, Element.LIGHT),
    _ranker("emilia", "Emilia", "Re:ZERO -Starting Life in Another World-", 26, 86, Element.ICE),
    _ranker("akane-kurokawa", "Akane Kurokawa", "Oshi no Ko", 27, 48, Element.MIND),
    _ranker("momo-yaoyorozu", "Momo Yaoyorozu", "My Hero Academia", 28, 70, Element.EARTH),
    _ranker("darkness", "Darkness", "KonoSuba: God's Blessing on This Wonderful World!", 29, 79, Element.EARTH),
    _ranker("mary-kikakujou", "Mary Kikakujou", "Busou Shoujo Machiavellianism", 30, 52, Element.FIRE),
    _ranker("nejire-hadou", "Nejire Hado", "My Hero Academia", 31, 74, Element.LIGHTNING),
    _ranker("mirajane-strauss", "Mirajane Strauss", "Fairy Tail", 32, 92, Element.DARK),
    _ranker("lucy-heartfilia", "Lucy Heartfilia", "Fairy Tail", 33, 84, Element.ARCANE),
    _ranker("midnight", "Midnight", "My Hero Academia", 34, 68, Element.DARK),
    _ranker("boa-hancock", "Boa Hancock", "One Piece", 35, 86, Element.MIND),
    _ranker("mikasa-ackerman", "Mikasa Ackerman", "Attack on Titan", 36, 84, Element.WIND),
    _ranker("rin-tohsaka", "Rin Tohsaka", "Fate/stay night", 37, 77, Element.FIRE),
    _ranker("cha-hae-in", "Cha Hae-In", "Solo Leveling", 38, 91, Element.LIGHT),
    _ranker("lilith-asami", "Lilith Asami", "Trinity Seven", 39, 72, Element.ARCANE),
    _ranker("erina-nakiri", "Erina Nakiri", "Food Wars!: Shokugeki no Soma", 40, 43, Element.NEUTRAL),
    _ranker("chisato-hasegawa", "Chisato Hasegawa", "The Testament of Sister New Devil", 41, 70, Element.DARK),
    _ranker("chelsea", "Chelsea", "Akame Ga Kill", 42, 65, Element.MIND),
    _ranker("rangiku-matsumoto", "Rangiku Matsumoto", "Bleach", 43, 78, Element.WIND),
    _ranker("jibril", "Jibril", "No Game No Life", 44, 97, Element.LIGHT),
    _ranker("venelana-gremory", "Venelana Gremory", "High School DxD", 45, 84, Element.DARK),
    _ranker("ino-yamanaka", "Ino Yamanaka", "Naruto", 46, 60, Element.MIND),
    _ranker("leone", "Leone", "Akame Ga Kill", 47, 83, Element.EARTH),
    _ranker("nezuko-kamado", "Nezuko Kamado", "Demon Slayer", 48, 86, Element.DARK),
    _ranker("kurumi-tokisaki", "Kurumi Tokisaki", "Date A Live", 49, 97, Element.DARK),
    _ranker("saeko-busujima", "Saeko Busujima", "Highschool of the Dead", 50, 84, Element.WIND),
    _ranker("irina-shidou", "Irina Shidou", "High School DxD", 51, 72, Element.LIGHT),
    _ranker("sinon", "Sinon", "Sword Art Online II", 52, 81, Element.WIND),
    _ranker("cana-alberona", "Cana Alberona", "Fairy Tail", 53, 67, Element.ARCANE),
    _ranker("xenovia", "Xenovia", "High School DxD", 54, 80, Element.LIGHT),
    _ranker("takane-takamine", "Takane Takamine", "Please Put Them On, Takamine-san", 55, 40, Element.NEUTRAL),
    _ranker("sayaka-kirasaka", "Sayaka Kirasaka", "Strike the Blood", 56, 68, Element.ICE),
    _ranker("reze", "Reze", "Chainsaw Man", 57, 89, Element.FIRE),
    _ranker("orihime-inoue", "Orihime Inoue", "Bleach", 58, 79, Element.LIGHT),
    _ranker("ako-tamaki", "Ako Tamaki", "And You Thought There Is Never a Girl Online?", 59, 40, Element.NEUTRAL),
    _ranker("tohka-yatogami", "Tohka Yatogami", "Date A Live", 60, 90, Element.LIGHTNING),
)


RECENT_2025_WAIFUS: tuple[WaifuDefinition, ...] = (
    _recent("maomao", "Maomao", "The Apothecary Diaries Season 2", 1, 45, Element.MIND),
    _recent("kaoruko-waguri", "Kaoruko Waguri", "The Fragrant Flower Blooms with Dignity", 2, 38, Element.LIGHT),
    _recent("momo-ayase", "Momo Ayase", "DAN DA DAN Season 2", 4, 80, Element.WIND),
    _recent("marin-kitagawa", "Marin Kitagawa", "My Dress-Up Darling Season 2", 5, 37, Element.LIGHT),
    _recent("ochako-uraraka", "Ochako Uraraka", "My Hero Academia FINAL SEASON", 6, 72, Element.WIND),
    _recent("oguri-cap", "Oguri Cap", "Umamusume: Cinderella Gray", 9, 76, Element.WIND),
    _recent("sakiko-togawa", "Sakiko “Oblivionis” Togawa", "BanG Dream! Ave Mujica", 10, 71, Element.DARK),
    _recent("mutsumi-wakaba", "Mutsumi “Mortis” Wakaba", "BanG Dream! Ave Mujica", 12, 69, Element.DARK),
    _recent("hinako-yaotose", "Hinako Yaotose", "The Shiunji Family Children", 13, 39, Element.WATER),
    _recent("hina-chono", "Hina Chono", "Blue Box", 14, 43, Element.WATER),
    _recent("chinatsu-kano", "Chinatsu Kano", "Blue Box", 15, 48, Element.WATER),
    _recent("nene-yashiro", "Nene Yashiro", "Toilet-Bound Hanako-kun Season 2", 16, 61, Element.DARK),
    _recent("nico-wakatsuki", "Nico Wakatsuki", "WITCH WATCH", 17, 66, Element.WIND),
    _recent("reiko-kujirai", "Reiko Kujirai", "Rurouni Kenshin", 18, 47, Element.LIGHT),
    _recent("banri-shiunji", "Banri Shiunji", "The Shiunji Family Children", 19, 42, Element.LIGHT),
    _recent("ouka-shiunji", "Ouka Shiunji", "The Shiunji Family Children", 20, 43, Element.ICE),
)


ALL_WAIFUS: tuple[WaifuDefinition, ...] = RANKED_WAIFUS + RECENT_2025_WAIFUS


def get_waifu_definition(character_id: str) -> WaifuDefinition:
    for definition in ALL_WAIFUS:
        if definition.id == character_id:
            return definition
    raise KeyError(character_id)
