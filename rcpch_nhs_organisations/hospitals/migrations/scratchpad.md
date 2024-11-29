# Steps to remove Jersey Boundary

1. In console delete all records in Jersey Boundary model
2. Remove Jersery Boundary model and makemigrations
3. Set country long lat to allow null and makemigrations
4. migrate
5. remove jersey folder and add jersey boundaries
6. python manage.py makemigrations hospitals --name add_jersey_boundaries_remap_identifier --empty