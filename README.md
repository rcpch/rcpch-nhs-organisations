# RCPCH NHS Organisations

<p align="center">
    <p align="center">
    <img align="center" src="/static/rcpch-logo.jpg" width='100px'/>
    </p>
</p>

## This is a Django 4.0 (django rest framework) project written in python 3.11.0, with a postgresql database. It (will) create a versioned database of all hospitals in the UK, updated periodically from ODS, but using the more updated information from the NHS API library. This information in turn will be checked for accuracy with NHS clinicians across the UK to maintain accuracy. It will run as a service

### Getting started

1. clone the repository
2. ``` s/docker-init ```

This will create a dockerised running API accessible at localhost on port 8005.

Note that it will not be possible to access the NHS API without an api key. You can sign up [here]('https://developer.api.nhs.uk/nhs-api') for one here. Add this to the environment variables in the docker-compose.dev-init.yml. Don't check your api key into git.
