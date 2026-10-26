#!/usr/bin/env python3
""" Select people who are regular or irregular and/or people who are in a tag or flow. Optionally add them to a tag/flow. """

import sys
import pprint
import argparse
import logging

from types import SimpleNamespace
from datetime import date, timedelta
from collections import defaultdict

import requests
import churchsuite

# The addressbook fields get replaced by module_scope() depending on --module
scope = ['attendance.read', 'addressbook.read', 'addressbook.write']

# Endpoint and field names differ per module, so look them up here:
#   people: endpoint that lists people, e.g. addressbook/contacts
#   id: query parameter that identifies a person, e.g. tag_resources?contact_id=n or flow_trackings?contact_ids[]=n
#   type: person type sent in the body when creating tag resources and flow trackings
modules = dict(
    addressbook=SimpleNamespace(people='contacts',  id='contact_id',  type='addressbook_contact'),
    children=   SimpleNamespace(people='children',  id='child_id',    type='children_child'),
    bookings=   SimpleNamespace(people='customers', id='customer_id', type='bookings_customer'),
    giving=     SimpleNamespace(people='givers',    id='giver_id',    type='giving_giver'),
)

def module_scope(module_name):
    """ Return the ChurchSuite scopes needed to run attenders on the given module, e.g. 'addressbook' """
    return [s.replace('addressbook', module_name) for s in scope]

# Exceptions
class AttendersError(Exception): pass
class NoTag(AttendersError): pass
class NoFlow(AttendersError): pass
class NoFlowTag(AttendersError): pass
class NoStage(AttendersError): pass
class FlowNotAcceptingPeople(AttendersError): pass
class InvalidStatus(AttendersError): pass

__version__ = churchsuite.__version__

def attendance_records(cs, weeks=31, days=['sunday']):
    """ Return dict of attendance records (by record_id) that fall on specified days in the previous number of weeks specified """
    today = date.today()
    # Get the date of n weeks ago
    is_after = today - timedelta(days=7*weeks)
    records = cs.get('attendance/records', days=days, is_after=is_after)
    records = {r.id: r for r in records}  # convert to dict by record ID
    return records

def add_attendance(cs, people, records):
    """ Given a SimpleNamespace list of people, add a dates_present attribute to each person
        such that people[n].dates_present will contain a set() of dates they attended.
        cs: Churchsuite instance
        records: a dict of attendance records produced by attendance_records()
    """
    for person in people:
        person.dates_present = set()
    if not records:
        return
    present = cs.get('attendance/record_contacts', record_ids=list(records.keys()))
    # Arrange people in a dict by person id so we can look up a person quickly to add each attendance date
    people_by_id = {p.id: p for p in people}
    for attender in present:
        person = people_by_id.get(attender.contact_id)
        if person:
            person.dates_present.add(records[attender.record_id].date)

def peoplize(n):
    """ Return '1 person' or 'n people' """
    return '1 person' if int(n)==1 else f'{n} people'

def name_key(person):
    """ Sort key by last, first, middle name. Treat missing or None names as '' so sorting never compares None with str """
    return tuple(getattr(person, field, None) or '' for field in ('last_name', 'first_name', 'middle_name'))

def append_defaults(l, defaults):
    """ Append items to list 'l' from 'defaults', as necessary to fill it up to len(defaults). Return 'l' """
    l += defaults[len(l):]
    return l

class Attenders:
    """ One run of attenders, holding its own options, ChurchSuite connection, output stream and tag cache """

    def __init__(self, args, cs=None, out=None):
        """ args: options returned by parse_args()
            cs: Churchsuite instance to use (default: log in as the API user given by churchsuite.user_auth())
            out: stream for printed output (default: sys.stdout)
        """
        self.args = args
        self.module = modules[args.module]
        self.cs = cs or churchsuite.Churchsuite(auth=churchsuite.user_auth(), scope=module_scope(args.module))
        self.out = out
        self._tag_cache = {}  # cache of (tag_name,status) which have had their members fetched

    def print(self, *values):
        print(*values, file=self.out or sys.stdout)

    def get_tag_id(self, tag_name, message=''):
        tag_id = self.cs.get_tag_id(tag_name, module=self.args.module)
        if tag_id is None:
            raise NoTag(f"Tag '{tag_name}' does not exist or is invisible to this user. {message}")
        return tag_id

    def get_flow_id(self, flow_name, message=''):
        flow_id = self.cs.get_flow_id(flow_name, module=self.args.module)
        if flow_id is None:
            raise NoFlow(f"Flow '{flow_name}' does not exist or is invisible to this user. {message}")
        return flow_id

    def get_tag_members(self, tag_name, status='active', message=''):
        """ Return a dict of (default active) tag members, indexed by their person_id; each dict value is set to a SimpleNamespace of the person's details.
            Cache results in case the same (tag_name, status) combination is requested later.
            Raise NoTag exception if tag doesn't exist, with 'message' appended to the error message.
            Raise InvalidStatus if status is not one of the options below.
        """
        status_options = ('active', 'archived', 'pending')
        if status not in status_options:
            raise InvalidStatus(f"Parameter 'status' must be one of: {status_options}")
        key = (tag_name, status)
        if key in self._tag_cache:
            return self._tag_cache[key]
        tag_id = self.get_tag_id(tag_name, message)
        people = self.cs.get(f'{self.args.module}/{self.module.people}', tag_ids=[tag_id], status=status)
        people = {person.id: person for person in people}
        self._tag_cache[key] = people
        return people

    def filter_by_attendance(self, people):
        """ Return list of people filtered by attendance specified in args.attendance """
        args = self.args
        if not args.attendance: return people
        # Merge in attendance records for each person
        records = attendance_records(self.cs, weeks=args.attendance[2])
        self.print(f"Examining {len(records)} sunday attendances recorded in the past {args.attendance[2]} weeks.")
        add_attendance(self.cs, people, records)
        # Categorise people by attendance frequency
        attender_by_freq = defaultdict(list)
        for person in people:
            freq = len(person.dates_present)
            attender_by_freq[freq].append(person)
        # Collate a list of both regulars and irregulars
        regulars, irregulars = [], []
        if args.verbose: self.print(f"\nIrregular attenders:")
        regular = False
        for freq in sorted(attender_by_freq):
            if freq >= args.attendance[1] and not regular:
                if args.verbose: self.print(f"\nRegular attenders:")
                regular = True
            if args.verbose:
                names = ', '.join(f"{p.first_name} {p.last_name}" for p in sorted(attender_by_freq[freq], key=name_key))
                self.print(f"  {freq}/{args.attendance[2]} sundays: {names}")
            if regular:
                regulars += attender_by_freq[freq]
            else:
                irregulars += attender_by_freq[freq]
        # Sort by just to keep output consistent (by last_name)
        regulars.sort(key=name_key)
        irregulars.sort(key=name_key)
        if args.verbose: self.print(f"\nFound {len(regulars)} regulars and {len(irregulars)} irregulars.")

        return irregulars if args.attendance[0] else regulars

    def filter_by_flow_tag(self, people, flow_tag_names=list(), message=''):
        """ Return a filtered list of people, including only those in the given list of flow or tag names.
            People in flow or tag names that are prefixed with '-' are NOT included. An empty list lets everyone through.
            Each name in the flow_tag_names list must reference a flow or tag name (flows take priority).
            NoFlowTag error will be raised if a flow or tag is not found
        """
        args, cs = self.args, self.cs
        if not flow_tag_names: return people
        inclusions, exclusions = set(), set()
        in_flows, not_in_flows = [], []
        for flow_tag in flow_tag_names:
            not_in = flow_tag.startswith('-')
            flow_tag = flow_tag[int(not_in):]
            flow_id = cs.get_flow_id(flow_tag, module=args.module) # return None if not found
            if flow_id:
                if args.verbose: self.print(f"{'Excluding' if not_in else 'Including'} people in flow '{flow_tag}'")
                (not_in_flows if not_in else in_flows).append(flow_id)
                continue
            try:
                tagged = self.get_tag_members(flow_tag, message=message)
                if args.verbose: self.print(f"{'Excluding' if not_in else 'Including'} people in tag '{flow_tag}'")
                if not_in:
                    exclusions |= set([*tagged])  # OR together all exclusion sets
                else:
                    inclusions |= set([*tagged])  # OR together all inclusion sets
            except NoTag:
                raise NoFlowTag(f"No flow or tag called '{flow_tag}' is visible to this user'. {message}")
        # Add people from flows to inclusions and exclusions outside the FOR loop above because
        # people in many flows can be requested all in one API request which is more efficent
        if in_flows:
            trackings = cs.get(f'{args.module}/flow_trackings', flow_ids=in_flows)
            inclusions |= set([t.person.id for t in trackings])
        if not_in_flows:
            trackings = cs.get(f'{args.module}/flow_trackings', flow_ids=not_in_flows)
            exclusions |= set([t.person.id for t in trackings])
        has_inclusions = any(not name.startswith('-') for name in flow_tag_names)
        return [p for p in people if (not has_inclusions or p.id in inclusions) and p.id not in exclusions]

    def run(self):
        """ Select people and update their tags/flows as specified by self.args """
        args, cs, module, print = self.args, self.cs, self.module, self.print
        get_tag_id, get_flow_id = self.get_tag_id, self.get_flow_id

        # Get all people and filter by specified attendance, tags and flows
        people = cs.get(f'{args.module}/{module.people}', status='active', q=args.fuzzy_filter if args.fuzzy_filter else None)  # fetch everyone
        people = self.filter_by_attendance(people)
        people = self.filter_by_flow_tag(people, args.filters, message='Specified with --in')
        print(f"* Identified {peoplize(len(people))}:", ', '.join(f"{p.first_name} {p.last_name}" for p in people) or 'nobody')

        # Remove the identified people from a tag if --remove-from-tag specified
        # Do this first so that --add-to-tag takes precedence if both are specified (to match flow behaviour, see below)
        if args.remove_from_tag and people:
            for tag_name in args.remove_from_tag:
                tag_id = get_tag_id(tag_name, message='Specified with --remove-from-tag')
                unremoved = []
                for person in people:
                    try:
                        cs.delete(f'{args.module}/tag_resources', tag_id=tag_id, **{module.id: person.id})
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code != 404:
                            raise
                        unremoved.append(person)
                print(f"{peoplize(len(people)-len(unremoved))} removed from tag '{tag_name}'")
                if unremoved:
                    print(f"  excluding {len(unremoved)} not in the tag:", ', '.join(f"{p.first_name} {p.last_name}" for p in unremoved))

        # Add the identified people to a tag if --add-to-tag specified
        if args.add_to_tag and people:
            for tag_name in args.add_to_tag:
                tag_id = get_tag_id(tag_name, message='Specified with --add-to-tag')
                for person in people:
                    cs.post(f'{args.module}/tag_resources', tag_id=tag_id, person=dict(id=person.id, type=module.type))
                print(f"{peoplize(len(people))} added to tag '{tag_name}'")

        # Remove the identified people from a flow if --remove-from-flow specified
        # Do this before add-to-flow so that someone can use both switches to move someone to a different stage
        if args.remove_from_flow and people:
            for flow_name in args.remove_from_flow:
                flow_id = get_flow_id(flow_name, message='Specified with --remove-from-flow')
                trackings = cs.get(f'{args.module}/flow_trackings', flow_ids=[flow_id], **{module.id + 's': [p.id for p in people]})
                trackings = {t.person.id: t for t in trackings}
                unremoved = []
                for person in people:
                    tracking = trackings.get(person.id)
                    if not tracking:
                        unremoved.append(person)
                        continue
                    try:
                        cs.delete(f'{args.module}/flow_trackings', tracking.id)
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code != 404:
                            raise
                        unremoved.append(person)
                print(f"{peoplize(len(people)-len(unremoved))} removed from flow '{flow_name}'")
                if unremoved:
                    print(f"  excluding {len(unremoved)} not in the flow:", ', '.join(f"{p.first_name} {p.last_name}" for p in unremoved))

        # Add the identified people to a flow if --add-to-flow specified
        if args.add_to_flow and people:
            for flow_spec in args.add_to_flow:
                # Split flow/stage (stage default = '')
                flow_name, stage = (flow_spec.split('/')+[''])[:2]
                # Add to flow at stage
                flow_id = get_flow_id(flow_name, message='Specified with --add-to-flow')
                stages = cs.get_stages(flow_id, module=args.module)
                if not stages:
                    raise NoStage(f"No stages exist in flow '{flow_name}' specified in --add-to-flow")
                stage_id = stages[0].id if stage == '' else cs.id_by_name(stages, stage)
                if not stage_id:
                    raise NoStage(f"Stage '{stage}' not found in flow '{flow_name}' specified in --add-to-flow")
                unadded = []
                for person in people:
                    try:
                        cs.post(f'{args.module}/flow_trackings', flow_id=flow_id, stage_id=stage_id, person=dict(id=person.id, type=module.type))
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code != 409:
                            raise
                        unadded.append(person)
                print(f"{peoplize(len(people)-len(unadded))} added to flow '{flow_name}'")
                if unadded:
                    print(f"  excluding {len(unadded)} already in the flow:", ', '.join(f"{p.first_name} {p.last_name}" for p in unadded))


def run(args, cs=None, out=None):
    """ Select people and update their tags/flows as specified by args from parse_args().
        See Attenders.__init__() for cs and out. Raise AttendersError or churchsuite.ChurchError on failure.
    """
    Attenders(args, cs, out).run()

def parse_attendance(freq):
    """ Parse attendance frequency argument of style: [<]4/8. """
    try:
        n, m = (int(x) for x in freq.removeprefix('<').split('/'))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{freq} invalid: must be two integers separated by /")
    if m < 1 or not 0 <= n <= m:
        raise argparse.ArgumentTypeError(f"{freq} invalid: m must be >0 and n must be 0-m in n/m")
    return [freq.startswith('<'), n, m]

def parse_csv(csv):
    """ Parse comma-separated-values into a list, stripping each value of spaces """
    return [v.strip() for v in csv.split(',')]

def build_parser():
    """ Return the argparse parser for attenders options """
    parser = argparse.ArgumentParser(
        prog='attenders',  # rather than sys.argv[0], which is e.g. gunicorn when parse_args() is called from a web app
        usage="%(prog)s [--help] [options]",
        formatter_class=argparse.RawDescriptionHelpFormatter,  # keep the description's line breaks
        description=
            "Select people who are regular or irregular and/or people who are in a tag or flow.\n"
            "Optionally add them to a tag/flow.\n"
            "\n"
            "Examples:\n"
            "  %(prog)s --attendance   4/8  --in=-Members,-Followup          --add-to-flow Followup\n"
            '  %(prog)s --attendance "<2/8"  --in=Members,-Followup,-ShutIn  --add-to-flow Followup\n'
            "  %(prog)s --in TrainingExpired --add-to-flow FollowupTraining",
    )

    # Select a different module than addressbook
    parser.add_argument('--module', type=str, default='addressbook', choices=modules,
        help="Select people from which module (default=addressbook)")

    # Filter by --attendance and flows/tags
    parser.add_argument('--attendance', type=parse_attendance,
        help='Select attendance frequency: e.g. 3/8 selects regulars: those who attend at least 3 of 8 weeks; but "<3/8" selects irregulars: those who attend less than that.')
    parser.add_argument('--in', metavar='flow,-flow,tag,-tag,...', type=parse_csv, default=list(),
        help="Include regulars or irregulars only if they are also in ANY of the specified list of flows or tags, and NOT in any of the -flows or -tags. "
            "A typical use would be finding newcomers who aren't members and aren't in a flow: regulars 4/8 --in=-Members,-Followup. "
            "Another example to find members who haven't come for a while: irregulars 1/8 --in=Members,-Followup. "
            "Note: Flow/tag names that contain spaces must be enclose in quotes.")
    # Taging
    parser.add_argument('--add-to-tag', type=parse_csv, default=list(),
        help="Add to the specified comma-spearated list of tags any people identified as regulars/irregulars.")
    parser.add_argument('--remove-from-tag', type=parse_csv, default=list(),
        help="Remove from the comma-separated list of tags any people identified as regulars/irregulars.")

    # Flow assignments
    parser.add_argument('--add-to-flow', type=parse_csv,
        help="Add to the specified comma-separated list of flow/stage any people identified as regulars/irregulars. Each flow may be followed by /stage (default=first). "
             "To move someone to a different stage in the flow, you can specify both --remove-from-flow and --add-to-flow on the same command line.")
    parser.add_argument('--remove-from-flow', type=parse_csv, default=list(),
        help="Remove from the comma-separated list of flows any people identified as regulars/irregulars.")

    parser.add_argument('-v', '--verbose', action='count', default=0, 
        help="Increase verbosity level (e.g., -vv) to, for example, "
            "print all regulars and irregulars found before they are filtered by any flows/tags specified by --in.")
    parser.add_argument('--version', action='store_true', 
        help="Print version number of this script and exit.")

    # For quick debugging using only one person, allows selecting a few people by fuzzy name search
    parser.add_argument('-f', '--fuzzy-filter', type=str, nargs='?', const='Berwyn Hoyt', default=None, help=argparse.SUPPRESS)
    return parser

def parse_args(argv=None):
    """ Return options parsed from argv (default sys.argv[1:]). On invalid options, print usage and raise SystemExit """
    parser = build_parser()
    args = parser.parse_args(argv)
    args.filters = getattr(args, 'in') # cannot read args.in because 'in' is a reserved word
    # ChurchSuite only records attendance for addressbook contacts
    if args.attendance and args.module != 'addressbook':
        parser.error("--attendance only works with --module=addressbook")
    return args

def main(argv=None):
    args = parse_args(argv)
    if args.version:
        print(__version__)
        return

    # Set logging level based on -v flag
    log_level = logging.WARNING - 10*args.verbose
    logging.basicConfig(level=log_level, format=f'%(levelname)s: %(message)s')

    try:
        run(args)
    except (AttendersError, churchsuite.ChurchError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
