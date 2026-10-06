# -*- coding: utf-8 -*-

from multiprocessing import get_context
from pathlib import Path
import tempfile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.db.models import ActiveMatch, Base, Card, CardInstance, GroupDrop, User
from src.services.battle_service import execute_turn, set_player_deck_and_lock
from src.services.drop_service import claim_card_drop
from src.services.match_service import accept_match_challenge, create_match_challenge, finish_match, validate_and_lock_staked_card


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _prepare_database(path: Path) -> None:
    engine = create_engine(_sqlite_url(path), connect_args={"timeout": 10.0})
    Base.metadata.create_all(engine)
    engine.dispose()


def _insert(path: Path, objects: list[object]) -> None:
    engine = create_engine(_sqlite_url(path), connect_args={"timeout": 10.0})
    with Session(engine) as session:
        session.add_all(objects)
        session.commit()
    engine.dispose()


def _run_two_processes(operation: str, path: Path, payload: dict) -> list[dict]:
    context = get_context("spawn")
    start_event = context.Event()
    ready_queue = context.Queue()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_worker,
            args=(operation, str(path), payload, start_event, ready_queue, result_queue),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for _ in processes:
        assert ready_queue.get(timeout=20) is True
    start_event.set()
    for process in processes:
        process.join(timeout=30)
        assert not process.is_alive()
        assert process.exitcode == 0
    return [result_queue.get(timeout=5) for _ in processes]


def _worker(operation, database_path, payload, start_event, ready_queue, result_queue):
    ready_queue.put(True)
    start_event.wait(timeout=20)
    try:
        engine = create_engine(_sqlite_url(Path(database_path)), connect_args={"timeout": 10.0})
        try:
            with Session(engine) as session:
                if operation == "claim_drop":
                    result = {"success": claim_card_drop(session, payload["drop_id"], payload["user_id"], payload["username"])[0]}
                elif operation == "create_match":
                    result = {"success": create_match_challenge(session, payload["group_id"], payload["player1_id"])[0]}
                elif operation == "accept_match":
                    result = {"success": accept_match_challenge(session, payload["match_id"], payload["player2_id"])[0]}
                elif operation == "lock_stake":
                    result = {"success": validate_and_lock_staked_card(session, payload["match_id"], payload["user_id"], payload["card_id"])[0]}
                elif operation == "lock_deck":
                    result = {"success": set_player_deck_and_lock(session, payload["match_id"], payload["player_id"], payload["deck"])}
                elif operation == "turn":
                    result = execute_turn(session, payload["match_id"], payload["player_id"])
                elif operation == "finish":
                    result = {"success": finish_match(session, payload["match_id"], payload["winner_id"])[0]}
                elif operation == "create_match_same_referee":
                    import src.services.match_service as match_service
                    original = match_service.get_available_referee
                    match_service.get_available_referee = lambda _session: "Cari"
                    try:
                        result = {"success": create_match_challenge(session, payload["group_id"], payload["player1_id"])[0]}
                    finally:
                        match_service.get_available_referee = original
                else:
                    raise AssertionError(operation)
        finally:
            engine.dispose()
        result_queue.put(result)
    except Exception as exc:
        result_queue.put({"worker_error": f"{type(exc).__name__}: {exc}"})


def _assert_results(results, expected_successes=1, expected_functional_errors=()):
    worker_errors = [item["worker_error"] for item in results if "worker_error" in item]
    assert not worker_errors, worker_errors
    assert sum(bool(item["success"]) for item in results) == expected_successes
    functional_errors = [
        item["error"]
        for item in results
        if not item["success"] and "error" in item
    ]
    assert functional_errors == list(expected_functional_errors)


def test_l02_claim_drop_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "economy.sqlite3"
        _prepare_database(path)
        _insert(path, [
            Card(id=1, name="Test Card", rarity="Common"),
            CardInstance(id="drop-card", card_id=1, owner_id=None, copy_number=1),
            GroupDrop(id=1, group_id=-1001, card_instance_id="drop-card", is_claimed=False),
        ])
        _assert_results(_run_two_processes("claim_drop", path, {"drop_id": 1, "user_id": 9001, "username": "winner"}))
        engine = create_engine(_sqlite_url(path))
        with Session(engine) as session:
            drop = session.get(GroupDrop, 1)
            card = session.get(CardInstance, "drop-card")
            assert drop.is_claimed is True and drop.claimed_by_id == 9001
            assert card.owner_id == 9001
        engine.dispose()


def test_l03_create_match_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "matches.sqlite3"
        _prepare_database(path)
        _insert(path, [User(id=1001)])
        _assert_results(_run_two_processes("create_match", path, {"group_id": -1001, "player1_id": 1001}))
        engine = create_engine(_sqlite_url(path))
        with Session(engine) as session:
            rows = session.scalars(select(ActiveMatch).where(
                ActiveMatch.status.in_(["WAITING", "IN_PROGRESS"]),
                (ActiveMatch.player1_id == 1001) | (ActiveMatch.player2_id == 1001),
            )).all()
            assert len(rows) == 1
        engine.dispose()


def test_l04_accept_match_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "matches.sqlite3"
        _prepare_database(path)
        _insert(path, [
            User(id=1001), User(id=2002),
            ActiveMatch(
                id="match-004", group_id=-1001, player1_id=1001, player2_id=0,
                p1_hp=100, p2_hp=100, current_turn_id=1001,
                current_turn_player_id=1001, status="WAITING", referee_name="Cari",
            ),
        ])
        _assert_results(_run_two_processes("accept_match", path, {"match_id": "match-004", "player2_id": 2002}))
        engine = create_engine(_sqlite_url(path))
        with Session(engine) as session:
            match = session.get(ActiveMatch, "match-004")
            assert match.status == "IN_PROGRESS" and match.player2_id == 2002
        engine.dispose()


def test_l05_stake_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "stake.sqlite3"
        _prepare_database(path)
        _insert(path, [
            User(id=1001), User(id=2002), Card(id=1, name="Stake", rarity="R"),
            CardInstance(id="stake-card", card_id=1, owner_id=1001, copy_number=1),
            ActiveMatch(
                id="match-005", group_id=-1001, player1_id=1001, player2_id=2002,
                p1_hp=100, p2_hp=100, current_turn_id=1001,
                current_turn_player_id=1001, status="WAITING_FOR_STAKES",
                referee_name="Cari",
            ),
        ])
        _assert_results(_run_two_processes("lock_stake", path, {"match_id": "match-005", "user_id": 1001, "card_id": "stake-card"}))
        engine = create_engine(_sqlite_url(path))
        with Session(engine) as session:
            card = session.get(CardInstance, "stake-card")
            match = session.get(ActiveMatch, "match-005")
            assert card.is_locked is True and match.p1_staked_card_id == "stake-card"
        engine.dispose()


def test_l06_deck_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "deck.sqlite3"
        _prepare_database(path)
        _insert(path, [
            User(id=1001), User(id=2002),
            Card(id=1, name="W", rarity="R"), Card(id=2, name="E", rarity="R"), Card(id=3, name="M", rarity="R"),
            CardInstance(id="card-w", card_id=1, owner_id=1001, copy_number=1),
            CardInstance(id="card-e", card_id=2, owner_id=1001, copy_number=1),
            CardInstance(id="card-m", card_id=3, owner_id=1001, copy_number=1),
            ActiveMatch(
                id="match-006", group_id=-1001, player1_id=1001, player2_id=2002,
                p1_hp=100, p2_hp=100, current_turn_id=1001,
                current_turn_player_id=1001, status="IN_PROGRESS", referee_name="Cari",
            ),
        ])
        deck={"waifu":{"id":"card-w"},"equip":{"id":"card-e"},"magic":{"id":"card-m"}}
        _assert_results(_run_two_processes("lock_deck", path, {"match_id":"match-006","player_id":1001,"deck":deck}))
        engine=create_engine(_sqlite_url(path))
        with Session(engine) as session:
            cards=session.scalars(select(CardInstance).where(CardInstance.id.in_(["card-w","card-e","card-m"]))).all()
            match=session.get(ActiveMatch,"match-006")
            assert all(c.is_locked for c in cards)
            assert {match.p1_waifu_instance_id,match.p1_equip_instance_id,match.p1_magic_instance_id}=={"card-w","card-e","card-m"}
        engine.dispose()


def test_l07_nonterminal_turn_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/"turn.sqlite3"
        _prepare_database(path)
        _insert(path,[User(id=1001),User(id=2002),ActiveMatch(
            id="match-007",group_id=-1001,player1_id=1001,player2_id=2002,
            p1_hp=1000,p2_hp=1000,current_turn_id=1001,current_turn_player_id=1001,
            status="IN_PROGRESS",referee_name="Cari")])
        _assert_results(_run_two_processes("turn",path,{"match_id":"match-007","player_id":1001}), expected_functional_errors=("No es tu turno de actuar.",))
        engine=create_engine(_sqlite_url(path))
        with Session(engine) as session:
            match=session.get(ActiveMatch,"match-007")
            assert match.p1_hp==1000 and match.p2_hp==950 and match.current_turn_player_id==2002
        engine.dispose()


def test_l07_terminal_turn_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/"terminal.sqlite3"
        _prepare_database(path)
        _insert(path,[User(id=1001),User(id=2002),ActiveMatch(
            id="match-008",group_id=-1001,player1_id=1001,player2_id=2002,
            p1_hp=1000,p2_hp=50,current_turn_id=1001,current_turn_player_id=1001,
            status="IN_PROGRESS",referee_name="Cari")])
        _assert_results(_run_two_processes("turn",path,{"match_id":"match-008","player_id":1001}), expected_functional_errors=("El duelo no está en curso.",))
        engine=create_engine(_sqlite_url(path))
        with Session(engine) as session:
            match=session.get(ActiveMatch,"match-008")
            assert match.status=="FINISHED" and match.p2_hp==0
        engine.dispose()


def test_l08_finish_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/"finish.sqlite3"
        _prepare_database(path)
        _insert(path,[
            User(id=1001),User(id=2002),
            Card(id=10,name="A",rarity="R"),Card(id=11,name="B",rarity="R"),Card(id=12,name="C",rarity="R"),
            CardInstance(id="stake-a",card_id=10,owner_id=1001,copy_number=1,is_locked=True),
            CardInstance(id="stake-b",card_id=11,owner_id=1001,copy_number=1,is_locked=True),
            CardInstance(id="stake-c",card_id=12,owner_id=2002,copy_number=1,is_locked=True),
            ActiveMatch(
                id="match-009",group_id=-1001,player1_id=1001,player2_id=2002,p1_hp=10,p2_hp=10,
                current_turn_id=1001,current_turn_player_id=1001,p1_staked_card_id="stake-b",
                p2_staked_card_id="stake-c",staked_card_instance_id="stake-a",staked_rarity="R",
                status="IN_PROGRESS",referee_name="Cari")])
        _assert_results(_run_two_processes("finish",path,{"match_id":"match-009","winner_id":1001}))
        engine=create_engine(_sqlite_url(path))
        with Session(engine) as session:
            match=session.get(ActiveMatch,"match-009")
            cards={c.id:c for c in session.scalars(select(CardInstance).where(CardInstance.id.in_(["stake-a","stake-b","stake-c"]))).all()}
            assert match.status=="FINISHED"
            assert match.staked_card_instance_id is None and match.p1_staked_card_id is None and match.p2_staked_card_id is None
            assert all(not c.is_locked for c in cards.values())
            assert cards["stake-a"].owner_id==1001 and cards["stake-b"].owner_id==1001 and cards["stake-c"].owner_id==1001
        engine.dispose()


def test_l09_referee_unique_index_two_processes():
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/"referee.sqlite3"
        _prepare_database(path)
        _insert(path,[User(id=1001)])
        _assert_results(_run_two_processes("create_match_same_referee",path,{"group_id":-1001,"player1_id":1001}))
        engine=create_engine(_sqlite_url(path))
        with Session(engine) as session:
            rows=session.scalars(select(ActiveMatch).where(
                ActiveMatch.referee_name=="Cari",
                ActiveMatch.status.in_(["WAITING","IN_PROGRESS"]),
            )).all()
            assert len(rows)==1
        engine.dispose()
