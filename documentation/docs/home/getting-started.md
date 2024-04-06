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

If you navigate to [https://rcpch-nhs-organisations.localhost/rcpch-census-platform/api/v1/swagger-ui/#/](https://rcpch-census-platform.localhost/organisations/api/v1/swagger-ui/#/) the Open API Specification and schemas are visible. If only the base url [https://rcpch-census-platform.localhost/rcpch-census-platform/api/v1/](https://organisations.localhost/organisations/api/v1/) is used, the django browsable API can be found.
