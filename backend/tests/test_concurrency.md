# Mandatory concurrency test

The production concurrency guarantee is implemented by `inventory_service.get_locked_inventory()` using deterministic cabin ordering and PostgreSQL `FOR UPDATE`. A full integration test should run against PostgreSQL and launch 20 async requests against the same sailing/cabin; exactly one request must create the hold and the other 19 must receive HTTP 409.
