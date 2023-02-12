# standard imports
import os
import requests

"""
This file contains functions that retrieves lists of organisations from ODS
They can be downloaded in different formats from here: https://digital.nhs.uk/services/organisation-data-service/export-data-files/csv-downloads/other-nhs-organisations
The base_url for the rest API is https://directory.spineservices.nhs.uk/ORD/2-0-0/
For a given ODSCode, the API returns
organisation - ODS code, name, open date, close  date, last change date and status if active or inactive
* address - house or flat number, line 1, line 2, line 3, town, postcode and country
* contacts - email, website, telephone and fax
* roles - primary and non-primary roles
* relationships - legal and operational relationships including history where it was captured by ODS
* succession - history of legal succession following reconfiguration or mergers
* additional attributes - data items included to support policy and pragmatic change

Organisations are categorised by PrimaryRoleID (eg organisations?PrimaryRoleId=RO197) which has an associated PrimaryRoleDescription (eg NHS Trust)
RO197 returns all NHS trusts
RO198 returns all NHS trust sites
RO142 returns all Welsh Local Health Boards
RO144 returns all Welsh Local Health Board sites
They are updated quarterly
They do not require authentication

eg: https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations?Limit=500&PrimaryRoleId=RO197 would return a list of organisations
with the structure:
        {
            "Name": "HERTFORDSHIRE PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST",
            "OrgId": "RWR",
            "Status": "Active",
            "OrgRecordClass": "RC1",
            "PostCode": "AL10 8YE",
            "LastChangeDate": "2020-04-06",
            "PrimaryRoleId": "RO197",
            "PrimaryRoleDescription": "NHS TRUST",
            "OrgLink": "https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/RWR"
        },

If searching by ODS Code, a more detailed object is returned:
eg: https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/RWR
returns:
        {
            "Organisation": {
                "Name": "HERTFORDSHIRE PARTNERSHIP UNIVERSITY NHS FOUNDATION TRUST",
                "Date": [
                    {
                        "Type": "Operational",
                        "Start": "2001-04-01"
                    }
                ],
                "OrgId": {
                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                    "assigningAuthorityName": "HSCIC",
                    "extension": "RWR"
                },
                "Status": "Active",
                "LastChangeDate": "2020-04-06",
                "orgRecordClass": "RC1",
                "GeoLoc": {
                    "Location": {
                        "AddrLn1": "THE COLONNADES",
                        "AddrLn2": "BEACONSFIELD CLOSE",
                        "Town": "HATFIELD",
                        "PostCode": "AL10 8YE",
                        "Country": "ENGLAND",
                        "UPRN": 10007553984
                    }
                },
                "Contacts": {
                    "Contact": [
                        {
                            "type": "tel",
                            "value": "01707 253800"
                        },
                        {
                            "type": "http",
                            "value": "HTTPS://WWW.HPFT.NHS.UK/"
                        }
                    ]
                },
                "Roles": {
                    "Role": [
                        {
                            "id": "RO197",
                            "uniqueRoleId": 102782,
                            "primaryRole": true,
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2001-04-01"
                                }
                            ],
                            "Status": "Active"
                        },
                        {
                            "id": "RO57",
                            "uniqueRoleId": 155264,
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2007-08-01"
                                }
                            ],
                            "Status": "Active"
                        }
                    ]
                },
                "Rels": {
                    "Rel": [
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2020-04-01"
                                }
                            ],
                            "Status": "Active",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "QM7"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO261",
                                    "uniqueRoleId": 300786
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 696688
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2019-04-01",
                                    "End": "2020-03-31"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "Q79"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO210",
                                    "uniqueRoleId": 202023
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 568962
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2016-01-29",
                                    "End": "2019-03-31"
                                },
                                {
                                    "Type": "Legal",
                                    "Start": "2015-04-01",
                                    "End": "2019-03-31"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "Q78"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO210",
                                    "uniqueRoleId": 202022
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 358954
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2014-09-01",
                                    "End": "2016-01-28"
                                },
                                {
                                    "Type": "Legal",
                                    "Start": "2013-04-01",
                                    "End": "2015-03-31"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "Q58"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO210",
                                    "uniqueRoleId": 163553
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 193512
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2006-07-01",
                                    "End": "2014-08-31"
                                },
                                {
                                    "Type": "Legal",
                                    "Start": "2006-07-01",
                                    "End": "2013-03-31"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "Q35"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO132",
                                    "uniqueRoleId": 137019
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 76203
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2001-04-01",
                                    "End": "2002-03-31"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "QEX"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO132",
                                    "uniqueRoleId": 100464
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 51797
                        },
                        {
                            "Date": [
                                {
                                    "Type": "Operational",
                                    "Start": "2002-04-01",
                                    "End": "2006-06-30"
                                }
                            ],
                            "Status": "Inactive",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "Q02"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO132",
                                    "uniqueRoleId": 21633
                                }
                            },
                            "id": "RE5",
                            "uniqueRelId": 71564
                        }
                    ]
                },
                "Succs": {
                    "Succ": [
                        {
                            "uniqueSuccId": 10500,
                            "Date": [
                                {
                                    "Type": "Legal",
                                    "Start": "2001-04-01"
                                }
                            ],
                            "Type": "Predecessor",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "RQJ"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO197",
                                    "uniqueRoleId": 37508
                                }
                            }
                        },
                        {
                            "uniqueSuccId": 23860,
                            "Date": [
                                {
                                    "Type": "Legal",
                                    "Start": "2001-04-01"
                                }
                            ],
                            "Type": "Predecessor",
                            "Target": {
                                "OrgId": {
                                    "root": "2.16.840.1.113883.2.1.3.2.4.18.48",
                                    "assigningAuthorityName": "HSCIC",
                                    "extension": "RC8"
                                },
                                "PrimaryRoleId": {
                                    "id": "RO197",
                                    "uniqueRoleId": 25581
                                }
                            }
                        }
                    ]
                }
            }
        }

Another resource is https://api.nhs.uk/service-search
there are 2 versions which can be specified in the request (?api-version=2)
This requires an api key
The parameters for this GET request include
?search= 
&
?searchFields=
The values for each of these parameters can be comma separated.
An example therefore would be https://api.nhs.uk/service-search?api-version=2&search=Hospital, NHS Sector&searchFields=OrganisationType,OrganisationSubType
This would return a list of organisations each one whose structure follows this pattern:
        {
            "@search.score": 4.7030263,
            "SearchKey": "X104820",
            "ODSCode": "NPE01",
            "OrganisationName": "The Retreat Hospital York",
            "OrganisationTypeId": "HOS",
            "OrganisationType": "Hospital",
            "OrganisationStatus": "Visible",
            "SummaryText": null,
            "URL": null,
            "Address1": "107 Heslington Road",
            "Address2": "",
            "Address3": "",
            "City": "York",
            "County": "North Yorkshire",
            "Latitude": 53.950824737548835,
            "Longitude": -1.0631204843521118,
            "Postcode": "YO10 5BN",
            "Geocode": {
                "type": "Point",
                "coordinates": [
                    -1.06312,
                    53.9508
                ],
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": "EPSG:4326"
                    }
                }
            },
            "OrganisationSubType": "NHS Sector",
            "OrganisationAliases": [],
            "ParentOrganisation": {
                "ODSCode": "NPE",
                "OrganisationName": "The Retreat Hospital"
            },
            "Services": [
                {
                    "ServiceName": "Eating disorders (inpatient)",
                    "ServiceCode": "SRV0034",
                    "ServiceDescription": "<p>This service is designed for women with complex needs, primarily with an eating disorder (Anorexia Nervosa, Bulimia Nervosa, Binge Eating Disorder and EDNOS).&nbsp; We specialise in treating people with more than one diagnosis which may include Personality Disorder (PD), Obsessive Compulsive Disorder (OCD) or complex Post Traumatic Stress Disorder (PTSD).</p>\r\n<p>Our eating disorder service is delivered on our <strong>Naomi unit</strong> where there is a full multidisciplinary team, including a Consultant Psychiatrist, General Practitioner (GP), Clinical Psychologist, Cognitive Behavioural Therapist, Dietitian, Occupational Therapist, Social Worker, Physiotherapist, Pharmacist&nbsp; and nursing staff.&nbsp; The team are all trained in Cognitive Behavioural Therapy (CBT) to varying levels and are experienced in working therapeutically with this patient group.</p>\r\n<p>This unit uses a recovery focused model made up of seven branches, including physical monitoring, physical activities, independent living, psychological, independent eating, self-catering and leave. &nbsp;The model has been designed to allow patients to work collaboratively with the team and be active in decision making in their own care, enabling them to set goals, plan, and evaluate their progression through recovery to independent living.</p>\r\n<p>The &ldquo;Pathways to Recovery&rdquo; has three stages:</p>\r\n<ul>\r\n<li>Medical stabilisation - the focus of this stage is on restoration of physical health.</li>\r\n<li>Gaining skills - the focus of this stage is to understand the patient&rsquo;s problems and develop new skills that aid recovery.&nbsp; Therapy sessions, groups and other individual interventions will help the patient to achieve this.</li>\r\n<li>Transferring skills - The focus of this stage is to transfer those skills a patient has learnt during their admission to outside of the hospital environment, such as home and local community.&nbsp;</li>\r\n</ul>\r\n<p>Click here for&nbsp;a video tour of the unit: <a href=\"http://youtu.be/wjxWY_vqmZM\">http://youtu.be/wjxWY_vqmZM</a></p>\r\n<p>Referral information can be found&nbsp;here: <a href=\"http://www.theretreatyork.org.uk/make-a-referral/healthcare-professionals.html\">http://www.theretreatyork.org.uk/make-a-referral/healthcare-professionals.html</a></p>",
                    "Contacts": [],
                    "ServiceProvider": {
                        "ODSCode": "NPE",
                        "OrganisationName": "The Retreat Hospital"
                    },
                    "Treatments": [],
                    "OpeningTimes": [],
                    "AgeRange": [],
                    "Metrics": []
                },
                {
                    "ServiceName": "Older people's services",
                    "ServiceCode": "SRV0069",
                    "ServiceDescription": "<p>These services offer specialist care to older adults who require hospital based treatment for mental health problems eg psychosis, depression, bipolar affective disorder or dementia. &nbsp;This includes people who are detained under the Mental Health Act or who require intensive levels of assessment, monitoring and treatment that is not possible in other settings. &nbsp;The service is needs led not age led.&nbsp;</p>\r\n<p>The multidisciplinary team is experienced in managing high risk challenging behaviours in a dignified manner and uses a person centred holistic approach. In addition to a full range of ancillary services&nbsp;our Specialist Older&nbsp;Adult Services have a dedicated full-time multidisciplinary team consisting of:</p>\r\n<ul>\r\n<li>Clinical Team Managers</li>\r\n<li>Consultant Psychiatrist</li>\r\n<li>Clinical Psychologist</li>\r\n<li>Social Worker</li>\r\n<li>Psychology assistants</li>\r\n<li>Occupational Therapists</li>\r\n<li>Physiotherapist</li>\r\n<li>Registered Mental Health Nurses</li>\r\n<li>Support Workers</li>\r\n<li>Involvement Worker</li>\r\n<li>Team Administrator</li>\r\n<li>Advocacy</li>\r\n<li>Activities Coordinator</li>\r\n</ul>\r\n<p>In addition to this, we have support from a Music Therapist, a Drama Therapist and a Dietitian.&nbsp; An independent advocacy service and Resident Quaker support us in looking after the rights and spiritual needs of the people we care for.&nbsp; A local GP practice visits weekly and also provides an emergency service.</p>\r\n<ul>\r\n<li><a href=\"http://www.theretreatyork.org.uk/our-services/residential-mental-health-services/older-adult-services/complex-dementia-care.html\">Complex Dementia Care</a></li>\r\n<li><a href=\"http://www.theretreatyork.org.uk/our-services/residential-mental-health-services/older-adult-services/older-adult-mental-health-assessment-and-longer-term-support.html\">Mental Health Assessment and Longer Term Support</a></li>\r\n<li><a href=\"http://www.theretreatyork.org.uk/our-services/residential-mental-health-services/older-adult-services/older-adult-mental-health-rehabilitation-service.html\">Mental Health Rehabilitation Service </a></li>\r\n</ul>",
                    "Contacts": [],
                    "ServiceProvider": {
                        "ODSCode": "NPE",
                        "OrganisationName": "The Retreat Hospital"
                    },
                    "Treatments": [],
                    "OpeningTimes": [],
                    "AgeRange": [],
                    "Metrics": []
                },
                {
                    "ServiceName": "Personality disorder services",
                    "ServiceCode": "SRV0079",
                    "ServiceDescription": "<p>The Personality Disorder services at The Retreat are formed of two units; The Kemp Unit and The Acorn Programme. The units are for women with complex needs, predominantly women who meet the criteria for borderline personality disorder and / or complex post traumatic stress disorder. The journey through the care pathway, entrance and exit points will be individual to each patient and dependant on levels of need and risk, readiness to change, engagement and service availability in the patient's home area.</p>\r\n<p>We work with both formal (people detained under the Mental Health Act) and informal individuals. However, we will only accept detained patients if they are involved in the decision making process and agree to admission. While primarily an unlocked recovery and rehabilitation pathway, a card access system on The Kemp Unit can offer increased containment for detained patients in crisis.</p>\r\n<p>This service benefits from a multidisciplinary team including but not limited to: Consultant Psychiatrist, Psychologist, Occupational Therapist. The service provides evidence based therapies such as <strong>Dialectical Behaviour Therapy</strong> and <strong>Cognitive Behavioural Therapy.</strong></p>\r\n<p>&nbsp;</p>",
                    "Contacts": [],
                    "ServiceProvider": {
                        "ODSCode": "NPE",
                        "OrganisationName": "The Retreat Hospital"
                    },
                    "Treatments": [],
                    "OpeningTimes": [],
                    "AgeRange": [],
                    "Metrics": []
                }
            ],
            "OpeningTimes": [],
            "Contacts": [],
            "Facilities": [],
            "Staff": [],
            "GSD": null,
            "LastUpdatedDates": {
                "OpeningTimes": null,
                "BankHolidayOpeningTimes": null,
                "DentistsAcceptingPatients": null,
                "Facilities": "2014-10-01T03:30:25.277Z",
                "HospitalDepartment": null,
                "Services": "2014-10-01T03:30:25.277Z",
                "ContactDetails": "2014-10-01T03:30:25.277Z",
                "AcceptingPatients": null
            },
            "AcceptingPatients": {
                "GP": null,
                "Dentist": []
            },
            "GPRegistration": null,
            "CCG": null,
            "RelatedIAPTCCGs": [],
            "CCGLocalAuthority": [],
            "Trusts": [],
            "Metrics": []
        },
"""


def all_nhs_hospitals_list():
    """
    GET request to NHS digital
    """
    url = "https://api.nhs.uk/service-search?api-version=2&search=Hospital&searchFields=OrganisationType"
    api_key = os.getenv("NHS_API-KEY")
    print(f"apikey {api_key}")
    headers = {"Content-Type": "application/json", "subscription-key": api_key}

    response = requests.request(
        method="POST",
        url="https://api.nhs.uk/service-search/search?api-version=2",
        headers=headers,
        data="""
                {
                    "filter": "OrganisationType eq 'Hospital'",
                    "orderby": "OrganisationName",
                    "top": 1,
                    "skip": 0,
                    "count": true
                }
        """,
    )

    if response.status_code == 404:
        print("Could not get ODS data from server...")
        return None
    if response.status_code == 401:
        print(response.reason)
        return None

    serialised = response.json()
    values = serialised["value"]

    return values
