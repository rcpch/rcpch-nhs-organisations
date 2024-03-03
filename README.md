# RCPCH NHS Organisations

<p align="center">
    <p align="center">
    <img align="center" src="/static/rcpch-logo.jpg" width='100px'/>
    </p>
</p>

## About this project

This is a Django 4.0 (django rest framework) project written in python 3.11.0, with a postgresql database. It (will) create a versioned database of all hospitals in the UK, updated periodically from the [Organisation Data Service](https://digital.nhs.uk/developer/api-catalogue/organisation-data-service-ord). This information in turn will be checked for accuracy with NHS clinicians across the UK to maintain accuracy. It will run as a service.

It will also be available as a python package.

### Getting started

1. clone the repository
2. ``` s/up ```

This will create a dockerised running API accessible at localhost on port 8003.

There is a more complete documentation site on port 8004.
