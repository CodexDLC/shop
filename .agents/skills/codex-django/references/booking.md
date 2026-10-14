# Booking integration

The library adapts Django models to the booking engine in `codex-services`. Reuse its availability and booking selectors; do not rebuild slot search in cabinet JavaScript or a second project algorithm.

## Models and availability

`codex_django.booking` exports `DjangoAvailabilityAdapter`, `BookingCacheAdapter`, booking contracts and abstract model bases. Model bases retain historical names including `AbstractBookableMaster` and `MasterDayOffMixin`; newer public contracts use resource terminology.

The project provides concrete resource, service, appointment, working-day, day-off and settings models with the expected fields and relationships. `DjangoAvailabilityAdapter` is configurable, but not an adapter for any arbitrary ORM schema: inspect its category/resource/service relation accesses before subclassing or wiring models.

Use `get_available_slots` and related selectors in `booking/selectors.py` for project views. Select timezone, date range and step deliberately; do not silently copy the defaults into a site's business policy.

## Persistence and concurrency

Use `create_booking`'s transaction/locking/revalidation path. It locks selected resources in a deterministic order, recomputes availability without relying on cached slots, persists, and invalidates after commit. A displayed available slot is not a reservation.

Multi-service persistence requires the project `BookingPersistenceHook.persist_chain` integration. Preserve `resource_id`, `resource_selections`, and `lock_resources` contracts where used. Do not bypass server revalidation because a client supplied a slot or chain preview.

## Cabinet integration

Implement project data/engine/workflow seams using `BookingProjectDataProvider`, `BookingEngineGateway`, `BookingWorkflowService` and `BookingBridge`. They describe what project implementations must supply; importing a protocol does not create a working ORM bridge.

Reuse booking state DTOs and presenters to produce picker, summary and modal UI. `BookingCabinetAvailabilityService` without a gateway yields no slots; an empty picker may indicate missing integration rather than no real availability. Keep availability logic in the engine boundary and presentation in cabinet templates.

Source: `booking/contracts.py`, `booking/adapters/`, `booking/selectors.py`, `booking/mixins/`, `booking/cabinet/`. Inspect actual files for current signatures and project extension requirements.
