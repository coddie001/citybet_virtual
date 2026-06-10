"""
Virtual kickoff timeline for fixtures within a league season.
"""
FIXTURE_INTERVAL_MS = 6 * 60 * 1000


def assign_show_at_ms(fixture_index: int) -> int:
    """Return cumulative virtual kickoff offset in milliseconds."""
    return fixture_index * FIXTURE_INTERVAL_MS
