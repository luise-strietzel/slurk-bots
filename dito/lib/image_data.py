# -*- coding: utf-8 -*-

# Wencke Liermann - wliermann@uni-potsdam.de
# University of Potsdam

# Tested on:
# Python 3.8.5
# Windows 10
"""Manage access to image data."""


import configparser
import csv
import random


class ImageData(dict):
    """Manage the access to image data.

    Mapping from room id to items left for this room.

    Args:
        path (str): Path to a valid csv file with two columns
            per row, containing the url of two paired up
            images.
        n (int): Number of images presented per
            participant per room.
        shuffle (bool): Whether to randomly sample images or
            select them one by one as present in the file.
            If more images are present than required per room
            and participant, the selection is without replacement.
            Otherwise it is with replacement.
        seed (int): Use together with shuffle to
            make the image presentation process reproducible.
    """
    def __init__(self, path=None, n=1, shuffle=False, seed=None):
        self._path = path
        self._n = n
        self._shuffle = shuffle

        self._images = None
        if seed is not None:
            random.seed(seed)

    @property
    def n(self):
        return self._n

    @classmethod
    def from_config(cls, config_file):
        """Create instance with attributes read from config file.

        Args:
            config_file (str): Valid path to a configuration file.
                See 'config.cfg' for an example.

        Returns:
            ImageData: Object for accessing image data.
        """
        config = configparser.ConfigParser()
        with open(config_file, 'r', encoding="utf-8") as conf:
            config.read_file(conf)

        data_obj = cls(
            path=config.get("IMAGES", "path"),
            n=config.getint("IMAGES", "n"),
            shuffle=config.getboolean("IMAGES", "shuffle"),
            seed=None if config.get("IMAGES", "seed") == "None"
                      else config.getint("IMAGES", "seed")
        )
        return data_obj

    def get_image_pairs(self, room_id):
        """Create a collection of image pair items.

        Each pair holds two url each to one image
        ressource. The image will be loaded from there.
        For local testing, you can host the images with python:
        ```python -m SimpleHTTPServer 8000```

        This functions remembers previous calls to itself,
        which makes it possible to split a file of items over
        several participants even for not random sampling.

        Args:
            room_id (str): Unique identifier of a task room.

        Returns:
            None
        """
        if self._images is None:
            # first time accessing the file
            # or a new access for each random sample
            self._images = self._image_gen()
        sample = []
        while len(sample) < self._n:
            try:
                new_img = next(self._images)
            except StopIteration:
                # we reached the end of the file
                # and start again from the top
                self._images = self._image_gen()
            else:
                sample.append(tuple(new_img))
        if self._shuffle:
            # implements reservoir sampling
            for img_line, img in enumerate(self._images, self._n):
                rand_line = random.randint(0, img_line)
                if rand_line < self._n:
                    sample[rand_line] = tuple(img)
            self._images = None
        self[room_id] = sample

    def _image_gen(self):
        """Generate one image pair at a time."""
        with open(self._path, 'r', newline='') as csv_file:
            csv_reader = csv.reader(csv_file)
            for pair in csv_reader:
                yield pair


if __name__ == "__main__":
    import os
    import sys
    import unittest

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(ROOT)

    from tests.test_image_data import TestImageData

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestImageData))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
