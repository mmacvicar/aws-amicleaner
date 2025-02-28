#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from builtins import input
from builtins import object
import sys

from botocore.config import Config
from amicleaner import __version__
from .core import AMICleaner, OrphanSnapshotCleaner
from .fetch import Fetcher
from .resources.config import MAPPING_KEY, MAPPING_VALUES, EXCLUDED_MAPPING_VALUES
from .resources.config import TERM, BOTO3_RETRIES
from .utils import Printer, parse_args


class App(object):

    def __init__(self, args):

        self.version = args.version
        self.mapping_key = args.mapping_key or MAPPING_KEY
        self.mapping_values = args.mapping_values or MAPPING_VALUES
        self.excluded_mapping_values = args.excluded_mapping_values or EXCLUDED_MAPPING_VALUES
        self.keep_previous = args.keep_previous
        self.check_orphans = args.check_orphans
        self.from_ids = args.from_ids
        self.full_report = args.full_report
        self.force_delete = args.force_delete
        self.ami_min_days = args.ami_min_days
        self.aws_region = args.aws_region

        self.mapping_strategy = {
            "key": self.mapping_key,
            "values": self.mapping_values,
            "excluded": self.excluded_mapping_values,
        }

    @property
    def aws_config(self):
        return Config(retries={'max_attempts': BOTO3_RETRIES}, region_name=self.aws_region)

    def fetch_candidates(self, available_amis=None, excluded_amis=None):

        """
        Collects created AMIs,
        AMIs from ec2 instances, launch configurations, autoscaling groups
        and returns unused AMIs.
        """
        f = Fetcher(config=self.aws_config)

        available_amis = available_amis or f.fetch_available_amis()
        excluded_amis = excluded_amis or []

        if not excluded_amis:
            fetch_instances = set(f.fetch_instances())
            fetch_unattached_lc = set(f.fetch_unattached_lc())
            fetch_unattached_lt = set(f.fetch_unattached_lt())
            fetch_zeroed_asg_lc = set(f.fetch_zeroed_asg_lc())
            fetch_zeroed_asg_lt = set(f.fetch_zeroed_asg_lt())
            fetch_default_lt = set(f.fetch_default_lt())
            fetch_aws_backup = set(f.fetch_aws_backup())

            if self.full_report:
                Printer.print_ami_ids_group("Excluded from not terminated EC2 instances",
                                            available_amis, fetch_instances)
                Printer.print_ami_ids_group("Excluded from launch configurations",
                                            available_amis, fetch_unattached_lc)
                Printer.print_ami_ids_group("Excluded from launch templates",
                                            available_amis, fetch_unattached_lt)
                Printer.print_ami_ids_group("Excluded from launch configurations in autoscaling groups with 0 capacity",
                                            available_amis, fetch_zeroed_asg_lc)
                Printer.print_ami_ids_group("Excluded from launch templates in autoscaling groups with 0 capacity",
                                            available_amis, fetch_zeroed_asg_lt)                                
                Printer.print_ami_ids_group("Excluded from launch target's default version",
                                            available_amis, fetch_zeroed_asg_lt)   
                Printer.print_ami_ids_group("Excluded from AWS Backup",
                                            available_amis, fetch_aws_backup) 
                            
            excluded_amis += fetch_instances
            excluded_amis += fetch_unattached_lc
            excluded_amis += fetch_unattached_lt
            excluded_amis += fetch_zeroed_asg_lc
            excluded_amis += fetch_zeroed_asg_lt
            excluded_amis += fetch_default_lt
            excluded_amis += fetch_aws_backup
            
        candidates = [v
                      for k, v
                      in available_amis.items()
                      if k not in excluded_amis]
        return candidates

    def prepare_candidates(self, candidates_amis=None):

        """ From an AMI list apply mapping strategy and filters """

        candidates_amis = candidates_amis or self.fetch_candidates()

        if not candidates_amis:
            return None

        
        c = AMICleaner(config=self.aws_config)

        mapped_amis = c.map_candidates(
            candidates_amis=candidates_amis,
            mapping_strategy=self.mapping_strategy,
        )

        if not mapped_amis:
            return None

        candidates = []
        report = dict()

        for group_name, amis in mapped_amis.items():
            group_name = group_name or ""

            if not group_name:
                report["Excluded (by mapping strategy)"] = amis
            else:
                reduced, keep_previous, keep_min_day = c.reduce_candidates(amis, self.keep_previous, self.ami_min_days)
                if reduced:
                    report[group_name] = reduced
                    candidates.extend(reduced)

                if keep_previous:
                    report[f"Excluded {group_name} (by keep previous)"] = keep_previous

                if keep_min_day:
                    report[f"Excluded {group_name} (by min day)"] = keep_min_day

        Printer.print_report(report, self.full_report)

        return candidates

    def prepare_delete_amis(self, candidates, from_ids=False):

        """ Prepare deletion of candidates AMIs"""

        failed = []

        if from_ids:
            print(TERM.bold("\nCleaning from {} AMI id(s) ...".format(
                len(candidates))
            ))
            failed = AMICleaner(config=self.aws_config).remove_amis_from_ids(candidates)
        else:
            print(TERM.bold("\nCleaning {} AMIs ...".format(len(candidates))))
            failed = AMICleaner(config=self.aws_config).remove_amis(candidates)

        if failed:
            print(TERM.red("\n{0} failed snapshots".format(len(failed))))
            Printer.print_failed_snapshots(failed)

    def clean_orphans(self):

        """ Find and removes orphan snapshots """

        cleaner = OrphanSnapshotCleaner(config=self.aws_config)
        snaps = cleaner.fetch()

        if not snaps:
            return

        Printer.print_orphan_snapshots(snaps)

        answer = input(
            "Do you want to continue and remove {} orphan snapshots "
            "[y/N] ? : ".format(len(snaps)))
        confirm = (answer.lower() == "y")

        if confirm:
            print("Removing orphan snapshots... ")
            count = cleaner.clean(snaps)
            print("\n{0} orphan snapshots successfully removed !".format(count))

    def print_defaults(self):

        print(TERM.bold("\nDefault values : ==>"))
        print(TERM.green("mapping_key : {0}".format(self.mapping_key)))
        print(TERM.green("mapping_values : {0}".format(self.mapping_values)))
        print(TERM.green("excluded_mapping_values : {0}".format(self.excluded_mapping_values)))
        print(TERM.green("keep_previous : {0}".format(self.keep_previous)))
        print(TERM.green("ami_min_days : {0}".format(self.ami_min_days)))

    @staticmethod
    def print_version():
        print(__version__)

    def run_cli(self):

        if self.check_orphans:
            self.clean_orphans()
            return

        if self.from_ids:
            self.prepare_delete_amis(self.from_ids, from_ids=True)
        else:
            # print defaults
            self.print_defaults()

            print(TERM.bold("\nRetrieving AMIs to clean ..."))
            candidates = self.prepare_candidates()

            if not candidates:
                sys.exit(0)

            delete = False

            if not self.force_delete:
                answer = input(
                    "Do you want to continue and remove {} AMIs "
                    "[y/N] ? : ".format(len(candidates)))
                delete = (answer.lower() == "y")
            else:
                delete = True

            if delete:
                self.prepare_delete_amis(candidates)


def main():

    args = parse_args(sys.argv[1:])
    if not args:
        sys.exit(1)

    app = App(args)

    if app.version is True:
        app.print_version()
    else:
        app.run_cli()


if __name__ == "__main__":
    main()
