import collections
import mraa
import os
import sys
import time
import io
import math
import struct


#Import things for pocketsphinx
#import pyaudio
import wave
import pocketsphinx as ps
import sphinxbase

#Import things for energy calibration
import audioop

class WaitTimeoutError(Exception): pass

class RequestError(Exception): pass

class UnknownValueError(Exception): pass

#This is my first time to write something this big in python hahaha
class AudioSource(object):
    def __init__(self):
        raise NotImplementedError("this is an abstract class")
    def __enter__(self):
        raise NotImplementedError("this is an abstract class")
    def __exit__(self, exc_type, exc_value, trace_back):
        raise NotImplementedError("this is an abstract class")

class Microphone(AudioSource):
    def __init__(self,sample_rate=16000,chunk_size=1024):
        # set up PyAudio
        self.pyaudio_module = self.get_pyaudio()
        audio = self.pyaudio_module.PyAudio()
        self.format = self.pyaudio_module.paInt16
        #self.SAMPLE_WIDTH = self.pyaudio_module.get_sample_sizes(self.format)
        self.SAMPLE_WIDTH = 2
        self.SAMPLE_RATE = sample_rate
        self.CHUNK = chunk_size
        self.audio = None
        self.stream = None
       
    @staticmethod
    def get_pyaudio():
        import pyaudio
        return pyaudio

    def __enter__(self):
        assert self.stream is None, "This audio source is already inside a context manager"
        self.audio = self.pyaudio_module.PyAudio()
        try:
            self.stream = Microphone.MicrophoneStream(
                self.audio.open(
                    channels=1, format=self.format, rate=self.SAMPLE_RATE, frames_per_buffer=self.CHUNK,
                    input = True # stream is an input stream
                )
            )
        except Exception:
            self.audio.terminate()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
        finally:
            self.stream = None
            self.audio.terminate()

    class MicrophoneStream(object):
        def __init__(self, pyaudio_stream):
            self.pyaudio_stream = pyaudio_stream
        def read(self, size):
            return self.pyaudio_stream.read(size)
        def close(self):
            try:
                if not self.pyaudio_stream.is_stopped():
                    self.pyaudio_stream.stop_stream()
            finally:
                self.pyaudio_stream.close()


class Recognizer(AudioSource):
    def __init__(self):
        self.energy_threshold = 100  #an initial value was set
        self.dynamic_energy_threshold = True
        self.dynamic_energy_adjustment_damping = 0.15
        self.dynamic_energy_ratio = 1.5
        self.pause_threshold = 0.8
        self.operation_timeout = None
        self.phrase_threshold = 0.3
        self.non_speaking_duration = 0.5

    def adjust_for_ambient_noise(self, source, duration=1):
        assert self.pause_threshold >= self.non_speaking_duration >=0

        seconds_per_buffer = (source.CHUNK + 0.0 )/source.SAMPLE_RATE
        elapsed_time = 0
        while True:
            elapsed_time += seconds_per_buffer
            if elapsed_time > duration:break
            buffer = source.stream.read(source.CHUNK)
            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)#energy of an audio signal
            print("energy of an audio signal is {}".format(energy))
            #dynamically adjust the energy threshold using asymmetric weighted average
            damping = self.dynamic_energy_adjustment_damping**seconds_per_buffer
            target_energy = energy * self.dynamic_energy_ratio
            self.energy_threshold = self.energy_threshold*damping+target_energy*(1-damping)
            print("updated energy_threshold is {}".format(self.energy_threshold))
    
    def listen(self, source, timeout=None):
        assert self.pause_threshold >= self.non_speaking_duration >=0
        print("Listening")
        seconds_per_buffer = (source.CHUNK + 0.0 )/source.SAMPLE_RATE
        #print("seconds per buffer is {}".format(seconds_per_buffer))
        non_speaking_buffer_count = int(math.ceil(self.non_speaking_duration / seconds_per_buffer))
        hold_number = 15
        count = 0
        elapsed_time = 0 #number of seconds of audio read
        buffer = b"" # an empty buffer means that the stream has ended
        while True:
            frames = collections.deque()
            frames_decode = collections.deque()
            count = 0

            #store audio input until the phrase starts
            while True:
                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0: break
                #frames.append(buffer)
                frames_decode.append(buffer)
                #if len(frames) > non_speaking_buffer_count:
                #    frames.popleft()
                if len(frames_decode) > hold_number:
                    frames_decode.popleft()

                energy = audioop.rms(buffer, source.SAMPLE_WIDTH) #energy for audio signal
                print("random energy of the audio signal is {}".format(energy))
                if energy > (self.energy_threshold + 50):
                    print("energy raise detected")
                    frames_decode.append(buffer)
                    if count == 1:
                        print("voice detected")
                        count = 0
                        break
                    count = count + 1
                if energy <= (self.energy_threshold + 50):
                    count = 0

                if self.dynamic_energy_threshold:
                    damping = self.dynamic_energy_adjustment_damping ** seconds_per_buffer
                    target_energy = energy * self.dynamic_energy_ratio
                    self.energy_threshold = self.energy_threshold * damping + target_energy * (1 - damping)
                    print("the new energy threshold is {}".format(self.energy_threshold))

            while True:
                seconds=1
                for i in range(0, int(source.SAMPLE_RATE/source.CHUNK*seconds)):
                    buffer = source.stream.read(source.CHUNK)
                    frames_decode.append(buffer)
                #print("complete buffer to be decoded is {}".format(frames_decode))
                print(int(source.SAMPLE_RATE/source.CHUNK*seconds))
                print(len(frames_decode))
                break
            print("done recording")    
            frame_data = b"".join(list(frames_decode))
            return frame_data

    def recognize_sphinx(self, frame_data):
        print("recognizing using PocketSphinx")
        LMD   = "/home/root/led-speech-edison/lm/0410.lm"
        DICTD = "/home/root/led-speech-edison/lm/0410.dic"
        decoder = ps.Decoder(lm=LMD, dict=DICTD)
        decoder.start_utt()
        decoder.process_raw(frame_data,False,True)
        decoder.end_utt()
        #print("decoder works fine")
        hypothesis = decoder.get_hyp()
        if hypothesis is not None:
            return hypothesis[0]
