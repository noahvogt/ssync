#!/usr/bin/env python3

import os
import sys
import shutil

from configparser import ConfigParser
from termcolor import colored
import colorama


def error_msg(msg: str):
    print(colored("[*] Error: {}".format(msg), "red"))
    sys.exit(1)


def log(message: str):
    print(colored("[*] {}".format(message), "green"))


class Ssync:
    def __init__(self):
        self.parse_config()

    def parse_config(self):
        config_parser = ConfigParser()
        config_parser.read("config.ini")
        try:
            self.rclone_remote_dir = config_parser["RCLONE"]["remote_dir"]
            self.rclone_local_dir = config_parser["RCLONE"]["local_dir"]
            self.obs_slides_dir = config_parser["OBS"]["slides_dir"]
            self.obs_target_subdir = config_parser["OBS"]["target_subdir"]
            self.obs_min_subdirs = int(config_parser["OBS"]["min_subdirs"])
        except KeyError:
            error_msg("configuration file 'config.ini' could not be parsed")
        log("configuration initialised")

    def sync_slide_repo(self):
        log("syncing with remote slide repository...")
        os.system(
            "rclone sync -v {} {}".format(
                self.rclone_remote_dir, self.rclone_local_dir
            )
        )

    def clear_obs_slides_dir(self):
        log("clearing obs slides directory...")
        for filename in os.listdir(self.obs_slides_dir):
            file_path = os.path.join(self.obs_slides_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                error_msg("Failed to delete %s. Reason: %s" % (file_path, e))

    def create_minimum_subdirs(self, count: int):
        if count >= self.obs_min_subdirs:
            return

        for number in range(count, self.obs_min_subdirs + 1):
            dirname = os.path.join(
                self.obs_slides_dir, self.obs_target_subdir + " " + str(number)
            )
            os.mkdir(dirname)

    def slide_selection_iterator(self):
        iterator_prompt = "Exit now? (default=no) [y/N]: "
        dir_list_str = ""
        for directory in os.listdir(self.rclone_local_dir):
            dir_list_str += directory + "\n"
        dir_list_str = dir_list_str[:-1]
        tempfile_str = ".chosen-tempfile"

        index = 0
        while True:
            index += 1
            prompt_answer = str(
                input(
                    "[{} {}] ".format(self.obs_target_subdir, index)
                    + iterator_prompt
                )
            )
            if prompt_answer.lower() == "y":
                self.create_minimum_subdirs(index)
                break

            dir_list_str = dir_list_str.replace("\n", "\\n")
            os.system(
                'printf "{}" | fzf > {}'.format(dir_list_str, tempfile_str)
            )

            with open(tempfile_str, mode="r") as tempfile_file_opener:
                chosen_slides = tempfile_file_opener.read()[:-1].strip()

            if len(chosen_slides) == 0:
                log("no slides chosen, skipping...")
            else:
                log(
                    "copying slides '{}' to '{} {}'...".format(
                        chosen_slides, self.obs_target_subdir, index
                    )
                )
                src_dir = os.path.join(self.rclone_local_dir, chosen_slides)
                dest_dir = os.path.join(
                    self.obs_slides_dir,
                    self.obs_target_subdir + " " + str(index),
                )
                shutil.copytree(src_dir, dest_dir)

        if os.path.isfile(tempfile_str):
            os.remove(tempfile_str)

    def execute(self):
        self.sync_slide_repo()
        self.clear_obs_slides_dir()
        self.slide_selection_iterator()


def main():
    colorama.init()

    ssync = Ssync()
    ssync.execute()


if __name__ == "__main__":
    main()
