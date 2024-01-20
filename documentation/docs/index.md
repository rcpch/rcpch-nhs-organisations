---
title: Introduction
author: Dr Simon Chapman
---
!!! info "Guidance for Researchers"
    Go to the [Researchers' Guide](./researchers/api.md) for guidance on retrieving census data.

## RCPCH NHS Organisations

This project is a python 3.11 / Django Rest Framework project providing NHS organisational data as a service.

In particular it serves the following:

1. **List of all secondary care organisations in the UK where children are cared for.**
This latter service in particular is important as such a list does not exist elsewhere - it pulls together acute and community hospitals across the UK, as well the NHS organisational boundaries within which they fall (Trust/Local Health Board, Integrated Care Board, NHS Region). It also references which Paediatric Diabetes Unit they form part of, or which OPEN UK children's epilepsy group they fall into.

This service supports all RCPCH applications, in particular the Epilepsy12 and National Paediatric Diabetes Audits.

They are though open to anyone and do not require authentication.

The project is dockerised, and has containers for [Postgresql](https://www.postgresql.org/), [redis](https://redis.com/), [celery](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html) and [celery-beat](https://docs.celeryq.dev/en/stable/reference/celery.beat.html) for async and scheduled tasks. This documentation is also in a separate container and built with [MkDocs](https://www.mkdocs.org/)

<p align="center">
    <p align="center">
    <img src='../docs/_assets/_images/rcpch-logo-mobile.4d5b446caf9a.svg' alt='RCPCH Logo'>
    </p>
</p>

## Why is it needed?

The [NHS Digital](https://digital.nhs.uk/services/spine) publishes all NHS Organisational data exhaustively - this project is not intended to replace it. There is a need though for RCPCH to be able to provide lists of organisations that care for children or are responsible for children's health, to inform research, audit and clinical practice. The project will build and maintain lists of these organisations and their relationships with each other, where possible maintaining the structure already provided by NHS Digital. It is a work in progress.

## Python packages

A further ambition of this project is to provide this list not only as an API, but also as a python package hosted on PyPi but regularly updated as organisational changes occur (such as take overs and mergers), so that it can be used by other projects as a dependency.
