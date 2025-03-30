---
title: Contributing
author: Dr Simon Chapman
---

The RCPCH Incubator development team work in the open and actively promote open source. All code is on our [Github](https://github.com/rcpch)

We encourage people interested in child health, data, medical software, data science and data visualisation to get involved in our projects. We follow an 'agile' way of working - read our [Playbook](https://playbook.rcpch.tech/) for more information.

## Github

### Deployment

Branch protection is applied to the `live` branch. This runs pytest on all pull requests before concurrently deploying to Azure and our documentation site on Github Pages.

To deploy to `live`:

1. Raise a pull request and await for approval - this will deploy both the code and the documentation.

To deploy only the documentation:

1. Raise a pull request. Ensure the pull request title beings with `[docs]` in square brackets.
