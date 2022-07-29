#!/usr/bin/env python3

import re
import os
import sys
import shutil

from configparser import ConfigParser
from termcolor import colored
import colorama

CHECKFILE = "slidegen-checkfile.txt"
CACHEFILE = "slidegen-cachefile.txt"

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

            self.slidegen_exe_path = config_parser["SLIDEGEN"]["exe_path"]
            self.slidegen_cache_dir = config_parser["SLIDEGEN"]["cache_dir"]

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
            except Exception as error:
                error_msg(
                    "Failed to delete %s. Reason: %s" % (file_path, error)
                )

    def create_minimum_subdirs(self, count: int):
        if count >= self.obs_min_subdirs:
            return

        for number in range(count, self.obs_min_subdirs + 1):
            dirname = os.path.join(
                self.obs_slides_dir, self.obs_target_subdir + " " + str(number)
            )
            os.mkdir(dirname)

    def slide_selection_iterator(self):
        iterator_prompt = "Exit now? [y/N]: "
        structure_prompt = (
            "Choose song structure (leave blank for full song)"
            + " eg. [1,R,2,R] / [1-4]: "
        )
        file_list_str = ""
        for file in os.listdir(self.rclone_local_dir):
            file_list_str += file + "\n"
        file_list_str = file_list_str[:-1]
        tempfile_str = ".chosen-tempfile"

        index = 0
        while True:
            index += 1
            input_song_prompt = "[{} {}] ".format(self.obs_target_subdir, index)
            prompt_answer = str(input(input_song_prompt + iterator_prompt))
            if prompt_answer.lower() == "y":
                self.create_minimum_subdirs(index)
                break

            file_list_str = file_list_str.replace("\n", "\\n")
            os.system(
                'printf "{}" | fzf > {}'.format(file_list_str, tempfile_str)
            )

            with open(
                tempfile_str, encoding="utf-8", mode="r"
            ) as tempfile_file_opener:
                chosen_song_file = tempfile_file_opener.read()[:-1].strip()

            if len(chosen_song_file) == 0:
                log("no slides chosen, skipping...")
            else:
                structure_prompt_answer = input(
                    input_song_prompt + structure_prompt
                )

                log(
                    "generating slides '{}' to '{} {}'...".format(
                        chosen_song_file, self.obs_target_subdir, index
                    )
                )
                src_dir = os.path.join(self.rclone_local_dir, chosen_song_file)
                dest_dir = os.path.join(
                    self.slidegen_cache_dir,
                    self.obs_target_subdir + " " + str(index),
                )
                os.mkdir(dest_dir)
                os.system(
                    'python3 "{}" "{}" "{}" "{}"'.format(
                        self.slidegen_exe_path,
                        src_dir,
                        dest_dir,
                        structure_prompt_answer,
                    )
                )

        if os.path.isfile(tempfile_str):
            os.remove(tempfile_str)

    def cachefiles_found(self):
        return os.path.isfile(
            os.path.join(self.slidegen_cache_dir, CHECKFILE)
        ) and os.path.isfile(os.path.join(self.slidegen_cache_dir, CACHEFILE))

    def syncing_needed(self) -> bool:
        if not self.cachefiles_found():
            return True

        log("checking for remote changes...")
        os.system(
            'rclone md5sum {} --checkfile {} > {} 2> {}'.format(
                self.rclone_remote_dir,
                os.path.join(self.slidegen_cache_dir, CHECKFILE),
                os.devnull,
                os.path.join(self.slidegen_cache_dir, CACHEFILE),
            )
        )

        with open(
            os.path.join(self.slidegen_cache_dir, CACHEFILE),
            mode="r",
            encoding="utf-8",
        ) as cachefile_reader:
            cachefile_content = cachefile_reader.readlines()
        for line in cachefile_content:
            if re.search(": ([0-9])+ differences found$", line):
                diffs = int(
                    line[line.rfind(":") + 1 : line.find("differences")]
                )
                return bool(diffs)
        return False

    def save_new_checkfile(self):
        log("saving new checkfile...")
        os.system(
            'rclone md5sum {} > "{}"'.format(
                self.rclone_remote_dir,
                os.path.join(self.slidegen_cache_dir, CHECKFILE),
            )
        )
        if not os.path.isfile(os.path.join(self.slidegen_cache_dir, CACHEFILE)):
            shutil.copyfile(
                os.path.join(self.slidegen_cache_dir, CHECKFILE),
                os.path.join(self.slidegen_cache_dir, CACHEFILE),
            )

    def execute(self):
        if self.syncing_needed():
            self.sync_slide_repo()
            self.save_new_checkfile()
        self.clear_obs_slides_dir()
        self.slide_selection_iterator()


def main():
    colorama.init()

    ssync = Ssync()
    ssync.execute()


if __name__ == "__main__":
    main()
