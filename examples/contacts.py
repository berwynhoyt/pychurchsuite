#!/usr/bin/env python3
# Example minimal program to print all the people in your database

import churchsuite

cs = churchsuite.Churchsuite(auth=churchsuite.user_auth(), scope=['addressbook.read'])
people = cs.get('addressbook/contacts', status='active')
for p in people:
	print(f"{p.first_name} {p.last_name}: {p.email}")
