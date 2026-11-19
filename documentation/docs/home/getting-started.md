---
title: Getting started
author: Dr Simon Chapman
---

## Getting Started

Written in python 3.11 and django-rest-framework, with a postgresql-gis backend.

The start scripts are all in the `s` folder. It may be necessary to change permissions to this folder first, from within the project root by:
`chmod+x ~/s`

**Note that nothing will work without a `.envs/.env` file with environment variables. An example file is provided.

The start script creates 8 linked docker containers under the umbrella name `rcpch-nhs-organisations`:

1. **django-1** The API
2. **postgis-1** The Postgresql-GIS database
3. **mkdocs-1** All documentation
4. **caddy-1** web server

Once all docker containers have been instantiated, django runs through the migrations which create the tables in the database and seed them with data. None of this data is proprietary and is openly available on the public internet. As the database is seeded, progress is logged to the console within the django container.

### Steps

1. clone the repo
2. ```s/up```

This will build the containers and perform the initial migration.

To seed the database:

1. `docker compose exec django python manage.py seed --model=all`

### Upgrading from Postgres 15

The local `postgis` service runs Postgres 18 (`postgis/postgis:18-3.6`). Postgres data directories are not compatible across major versions, so the compose file uses a new volume, `postgis-18-data`. After pulling this change a fresh, empty database is created; either reseed it (above), or carry your existing data across:

```bash
# 1. Before upgrading, dump the old Postgres 15 database
docker compose exec postgis pg_dumpall -U "$POSTGRES_USER" > pg15-dump.sql

# 2. Pull the upgrade and start the new Postgres 18 container
docker compose up -d postgis

# 3. Restore into it
docker compose exec -T postgis psql -U "$POSTGRES_USER" -d postgres < pg15-dump.sql
```

Once you are happy, the old volume (`<project>_postgis-data`) can be removed with `docker volume rm`.

If you navigate to [the Open API Specification](https://rcpch-nhs-organisations.azurewebsites.net/swagger-ui/)) the schemas are visible. If only the [base url](https://rcpch-nhs-organisations.azurewebsites.net/) is used, the django browsable API can be found.
