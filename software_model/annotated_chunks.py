"""This module is an encapsulator for the AnnotatedChunks class."""
import csv
from math import ceil
import random as rand
import numpy as np
from scipy.io import wavfile
from software_model import utility_functions as utils
from software_model.constants import DATA_FILES_LOCATION, DOWNSAMPLE_FACTOR, NUM_SAMPS_IN_CHUNK
from software_model.chunks import Chunks

class AnnotatedChunks(Chunks):
    """This class is representative of an element of a partioned sound file."""

    def __init__(self, file_list):
        Chunks.__init__(self, file_list)
        
        self._spk1 = self.get_speaker('_Spk1')
        self._spk2 = self.get_speaker('_Spk2')
      

    def get_speaker(self, ext):
        """This method reads in speaking/non-speaking data from a csv file for a given speaker."""
        return list(self.read_annotations_from_csv(f, ext) for f in self._file_list)

    def read_annotations_from_csv(self, file_name, ext):
        """This method reads and parses the speaking/non-speaking data from a csv file."""
        spk = []
        with open(DATA_FILES_LOCATION + file_name + ext + '.csv', 'r') as file_being_read:
            reader = csv.reader(file_being_read)
            # Skip the header line
            next(file_being_read)
            for row in reader:
                spk.append(np.array(row[1:3], dtype='float32'))
        return np.array(spk)

    def get_annotated_chunk(self, file_index, chunk_index):
        """Retrives a specified chunk given a file index and chunk index"""

        spk1 = self._spk1[file_index]
        spk2 = self._spk2[file_index]

        start = chunk_index * NUM_SAMPS_IN_CHUNK
        end = start + NUM_SAMPS_IN_CHUNK

        midpoint_samp = (start + end) // 2
        midpoint_sec = midpoint_samp / self._samp_rate

        spk1_bin = np.digitize(midpoint_sec, spk1[:, 0])
        spk2_bin = np.digitize(midpoint_sec, spk2[:, 0])

        # If the midpoint of the chunk is part of the padded section,
        # There is no speaking here
        if spk1_bin >= spk1.shape[0]:
            spk1_status = 0
        else:
            spk1_status = int(spk1[spk1_bin, 1])

        if spk2_bin >= spk2.shape[0]:
            spk2_status = 0
        else:
            spk2_status = int(spk2[spk2_bin, 1])
            
        chunk = self.get_chunk(file_index, chunk_index)
        
        return chunk, [spk1_status, spk2_status]

    def get_random_annotated_chunk(self):
        """Gets a random chunk from a random file provided in the class initialization."""

        file_index = rand.randint(0, len(self._audio) - 1)
        audio_file = self._audio[file_index]
        num_chunks_in_file = ceil(audio_file.shape[0] / NUM_SAMPS_IN_CHUNK)
        chunk_index = rand.randint(0, num_chunks_in_file - 1)

        return self.get_annotated_chunk(file_index, chunk_index)

    def get_batch_of_random_annotated_chunks(self, batch_size):
        """Returns a batch of the given size composed of random chunks."""

        batch = []
        response_variables = []

        for _ in range(batch_size):
            chunk, status = self.get_random_annotated_chunk()
            chunk = chunk.reshape([1, NUM_SAMPS_IN_CHUNK, 2, 1])
            batch.append(chunk)
            response_variables.append(status)

        batch = np.concatenate(batch, axis=0)
        response_variables = np.array(response_variables)

        return batch, response_variables
