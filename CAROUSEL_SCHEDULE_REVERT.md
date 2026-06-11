# Revert wall-clock carousel scheduling

If the new schedule causes issues, revert without code changes:

```bash
export CAROUSEL_SCHEDULE_MODE=legacy
./run.sh stop && ./run.sh all
```

Then hard-refresh the frontend.

**Legacy mode restores:**
- Virtual `show_at_ms` promotion via `promote_ready_to_live`
- Frontend carousel loaded from per-league `/fixtures` (old `loadCarouselQueue`)

**Wall-clock mode (default):**
- `CAROUSEL_SCHEDULE_MODE=wall_clock` or unset
- Carousel from `GET /carousel`
- Real-time `scheduled_start_at` in `fixture.predictions._scheduled_start_at`
