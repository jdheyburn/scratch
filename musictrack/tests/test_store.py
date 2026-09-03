"""Decisions that outlive a run."""

from musictrack.store import Dismissals


def test_a_dismissal_is_remembered(tmp_path):
    store = Dismissals(tmp_path / "db.sqlite")
    store.add("bandcamp-wishlist", "123", "own the digital, want the vinyl")
    assert store.hidden() == {("bandcamp-wishlist", "123"): "own the digital, want the vinyl"}


def test_dismissing_twice_updates_rather_than_duplicates(tmp_path):
    store = Dismissals(tmp_path / "db.sqlite")
    store.add("spotify", "abc", "first")
    store.add("spotify", "abc", "second")
    assert store.hidden() == {("spotify", "abc"): "second"}


def test_the_same_ref_in_two_sources_is_two_dismissals(tmp_path):
    store = Dismissals(tmp_path / "db.sqlite")
    store.add("spotify", "1", "")
    store.add("bandcamp-wishlist", "1", "")
    assert len(store.hidden()) == 2


def test_an_empty_store_hides_nothing(tmp_path):
    assert Dismissals(tmp_path / "db.sqlite").hidden() == {}


def test_the_database_survives_being_reopened(tmp_path):
    path = tmp_path / "db.sqlite"
    Dismissals(path).add("spotify", "1", "keep")
    assert Dismissals(path).hidden() == {("spotify", "1"): "keep"}


def test_the_parent_directory_is_created(tmp_path):
    store = Dismissals(tmp_path / "nested" / "deeper" / "db.sqlite")
    store.add("spotify", "1", "")
    assert store.hidden()
