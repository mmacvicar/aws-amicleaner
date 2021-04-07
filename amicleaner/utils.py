#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from builtins import object
import argparse

from prettytable import PrettyTable

from .resources.config import KEEP_PREVIOUS, AMI_MIN_DAYS


class Printer(object):

    @staticmethod
    def print_ami_ids_group(group_name, amis_dict, ami_ids):
        filtered_amis = []
        additional_amis_ids = []

        for ami_id in ami_ids:
            ami = amis_dict.get(ami_id)
            if ami:
                filtered_amis.append(ami)
            else:
                additional_amis_ids.append(ami_id)

        Printer._print_ami_ids_group(group_name, filtered_amis)
        if additional_amis_ids:
            print(group_name, "(other ids)")
            groups_table = PrettyTable(["AMI ID"])
            for ami_id in additional_amis_ids:
                groups_table.add_row([
                    ami_id
                ])

            print(groups_table.get_string(sortby="AMI ID"), "\n\n")

    """ Pretty table prints methods """
    @staticmethod
    def print_report(candidates, full_report=False):

        """ Print AMI collection results """

        if not candidates:
            return

        groups_table = PrettyTable(["Group name", "candidates"])

        for group_name, amis in candidates.items():
            groups_table.add_row([group_name, len(amis)])
            if full_report:
                Printer._print_ami_ids_group(group_name, amis)

        print("\nAMIs to be removed:")
        print(groups_table.get_string(sortby="Group name"))

    @staticmethod
    def _print_ami_ids_group(group_name, amis):
        amis_table = Printer._prepare_ami_table(amis)
        print(group_name)
        print(amis_table.get_string(sortby="Creation Date"), "\n\n")

    @staticmethod
    def _prepare_ami_table(amis):
        eligible_amis_table = PrettyTable(
            ["AMI ID", "AMI Name", "Creation Date", "Tags"]
        )
        for ami in amis:
            eligible_amis_table.add_row([
                ami.id,
                ami.name,
                ami.creation_date,
                Printer.tags_to_string(ami.tags)
            ])

        return eligible_amis_table

    @staticmethod
    def print_failed_snapshots(snapshots):

        snap_table = PrettyTable(["Failed Snapshots"])

        for snap in snapshots:
            snap_table.add_row([snap])
        print(snap_table)

    @staticmethod
    def print_orphan_snapshots(snapshots):

        snap_table = PrettyTable(["Orphan Snapshots"])

        for snap in snapshots:
            snap_table.add_row([snap])
        print(snap_table)

    @staticmethod
    def tags_to_string(tags):
        if tags is None:
            return ""

        tag_values = []
        for tag in tags:
            tag_values.append(f"{tag.key} => {tag.value}")

        return "; ".join(sorted(tag_values))


def parse_args(args):
    parser = argparse.ArgumentParser(description='Clean your AMIs on your '
                                                 'AWS account. Your AWS '
                                                 'credentials must be sourced')

    parser.add_argument("-v", "--version",
                        dest='version',
                        action="store_true",
                        help="Prints version and exits")

    parser.add_argument("--from-ids",
                        dest='from_ids',
                        nargs='+',
                        help="AMI id(s) you simply want to remove")

    parser.add_argument("--full-report",
                        dest='full_report',
                        action="store_true",
                        help="Prints a full report of what to be cleaned")

    parser.add_argument("--mapping-key",
                        dest='mapping_key',
                        help="How to regroup AMIs : [name|tags]")

    parser.add_argument("--mapping-values",
                        dest='mapping_values',
                        nargs='+',
                        help="List of values for tags or name")

    parser.add_argument("--excluded-mapping-values",
                        dest='excluded_mapping_values',
                        nargs='+',
                        help="List of values to be excluded from tags")

    parser.add_argument("--keep-previous",
                        dest='keep_previous',
                        type=int,
                        default=KEEP_PREVIOUS,
                        help="Number of previous AMI to keep excluding those "
                             "currently being running")

    parser.add_argument("-f", "--force-delete",
                        dest='force_delete',
                        action="store_true",
                        help="Skip confirmation")

    parser.add_argument("--check-orphans",
                        dest='check_orphans',
                        action="store_true",
                        help="Check and clean orphaned snapshots")

    parser.add_argument("--ami-min-days",
                        dest='ami_min_days',
                        type=int,
                        default=AMI_MIN_DAYS,
                        help="Number of days AMI to keep excluding those "
                             "currently being running")

    parsed_args = parser.parse_args(args)
    if parsed_args.mapping_key and not parsed_args.mapping_values:
        print("missing mapping-values\n")
        parser.print_help()
        return None

    return parsed_args
